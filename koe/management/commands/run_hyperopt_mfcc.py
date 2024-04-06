import os
import pickle

from django.core.management.base import BaseCommand

import numpy as np
from hyperopt import Trials, fmin, hp, tpe
from scipy.stats import zscore

from koe.aggregator import aggregator_map
from koe.management.commands.extract_mfcc_multiparams import extract_mfcc_multiparams
from koe.management.commands.lstm import exclude_no_labels, get_labels_by_sids
from koe.ml_utils import classifiers, get_ratios
from koe.model_utils import get_or_error
from koe.models import Aggregation, Database
from koe.rnn_models import EnumDataProvider
from koe.storage_utils import get_sids_tids
from koe.utils import split_classwise
from root.models import User


def perform_k_fold(classifier, tvset, nfolds, v2a_ratio, nlabels, **classifier_args):
    """
    Perform k-fold validation
    :param v2a_ratio: ratio between validation set and (valid + train) set
    :param nfolds: number of folds
    :param tvset: data set for train+validation data. This should not contain the test set
    :return:
    """
    tvset.make_folds(nfolds, v2a_ratio)
    scores = []
    for i in range(nfolds):
        trainset, validset = tvset.get_fold(i)
        train_x = np.array(trainset.data)
        train_y = np.array(trainset.labels, dtype=np.int32)
        valid_x = np.array(validset.data)
        valid_y = np.array(validset.labels, dtype=np.int32)

        score, label_hits, label_misses, importances = classifier(
            train_x, train_y, valid_x, valid_y, nlabels, **classifier_args
        )
        scores.append(score)
    return np.mean(scores)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--classifier",
            action="store",
            dest="clsf_type",
            required=True,
            type=str,
            help="Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda",
        )

        parser.add_argument(
            "--database-name",
            action="store",
            dest="database_name",
            required=True,
            type=str,
            help="E.g Bellbird, Whale, ..., case insensitive",
        )

        parser.add_argument(
            "--annotator-name",
            action="store",
            dest="annotator_name",
            default="superuser",
            type=str,
            help="Name of the person who owns this database, case insensitive",
        )

        parser.add_argument(
            "--label-level",
            action="store",
            dest="label_level",
            default="label",
            type=str,
            help="Level of labelling to use",
        )

        parser.add_argument(
            "--min-occur",
            action="store",
            dest="min_occur",
            default=2,
            type=int,
            help="Ignore syllable classes that have less than this number of instances",
        )

        parser.add_argument(
            "--ipc",
            action="store",
            dest="ipc",
            default=None,
            type=int,
            help="Use this value as number of instances per class. Must be <= min-occur",
        )

        parser.add_argument(
            "--ratio",
            action="store",
            dest="ratio",
            required=False,
            default="80:10:10",
            type=str,
        )

        parser.add_argument("--profile", dest="profile", action="store", required=False)

        parser.add_argument("--load-dir", dest="load_dir", action="store", required=True)

    def handle(self, *args, **options):
        clsf_type = options["clsf_type"]
        database_name = options["database_name"]
        annotator_name = options["annotator_name"]
        label_level = options["label_level"]
        min_occur = options["min_occur"]
        ipc = options["ipc"]
        ratio_ = options["ratio"]
        profile = options.get("profile", None)
        load_dir = options["load_dir"]

        tsv_file = profile + ".tsv"
        trials_file = profile + ".trials"

        if ipc is not None:
            assert ipc <= min_occur, "Instances per class cannot exceed as min-occur"
            ipc_min = ipc
            ipc_max = ipc
        else:
            ipc_min = min_occur
            ipc_max = int(np.floor(min_occur * 1.5))

        train_ratio, valid_ratio, test_ratio = get_ratios(ratio_)

        variables = dict(open_mode="w")

        assert clsf_type in classifiers.keys(), "Unknown _classify: {}".format(clsf_type)
        classifier = classifiers[clsf_type]

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        aggregations = Aggregation.objects.filter(enabled=True).order_by("id")
        aggregators = [aggregator_map[x.name] for x in aggregations]

        _sids, _tids = get_sids_tids(database)
        _labels, no_label_ids = get_labels_by_sids(_sids, label_level, annotator, min_occur)
        if len(no_label_ids) > 0:
            _sids, _tids, _labels = exclude_no_labels(_sids, _tids, _labels, no_label_ids)

        unique_labels, enum_labels = np.unique(_labels, return_inverse=True)
        fold = split_classwise(
            enum_labels,
            ratio=test_ratio,
            limits=(ipc_min, ipc_max),
            nfolds=1,
            balanced=True,
        )
        train = fold[0]["train"]
        test = fold[0]["test"]
        all_indices = np.concatenate((train, test))

        tids = _tids[all_indices]
        labels = _labels[all_indices]

        params_names = []
        params_converters = []
        params_count = 0

        def loss(params):
            mfcc_args = {}
            classifier_args = {}
            for i in range(params_count):
                param_name = params_names[i]
                param_converter = params_converters[i]
                param_value = params[i]

                if param_name.startswith("mfcc:"):
                    real_name = param_name[5:]
                    mfcc_args[real_name] = param_converter(param_value)
                else:
                    classifier_args[param_name] = param_converter(param_value)

            _fmin = mfcc_args["fmin"]
            _fmax = mfcc_args["fmax"]
            _ncep = mfcc_args["ncep"]

            extract_mfcc_multiparams(database_name, load_dir, _ncep, _fmin, _fmax)

            data = []
            tid2rows = {tid: [] for tid in tids}

            for aggregator in aggregators:
                agg_saved_file = "database={}-feature=mfcc-aggregator={}-fmin={}-fmax={}-ncep={}.pkl".format(
                    database_name, aggregator.get_name(), _fmin, _fmax, _ncep
                )
                agg_saved_file_loc = os.path.join(load_dir, agg_saved_file)

                with open(agg_saved_file_loc, "rb") as f:
                    tid2aval = pickle.load(f)
                    for tid in tids:
                        val = tid2aval[tid]
                        row = tid2rows[tid]
                        row.append(val)

            for tid in tids:
                row = tid2rows[tid]
                row = np.hstack(row).T
                data.append(row)
            data = np.array(data)
            data = zscore(data)
            data[np.where(np.isnan(data))] = 0
            data[np.where(np.isinf(data))] = 0

            unique_labels = np.unique(labels)
            nlabels = len(unique_labels)

            dp = EnumDataProvider(data, labels, balanced=True)
            trainvalidset, _ = dp.split(0, limits=(min_occur, int(np.floor(min_occur * 1.5))))

            v2t_ratio = valid_ratio / (train_ratio + valid_ratio)
            nfolds = int(np.floor(1.0 / v2t_ratio + 0.01))

            print(classifier_args)
            score = perform_k_fold(classifier, trainvalidset, nfolds, v2t_ratio, nlabels, **classifier_args)
            return 1.0 - score

        n_estimators_choices = hp.uniform("n_estimators", 40, 100)
        min_samples_split_choices = hp.uniform("min_samples_split", 2, 21)
        min_samples_leaf_choices = hp.uniform("min_samples_leaf", 1, 20)
        gamma_choices = hp.uniform("gamma", 0.1, 10)
        c_choices = hp.loguniform("C", -1, 2)
        hidden_layer_size_choices = hp.uniform("hidden_layer_sizes", 100, 1000)

        choices = {
            "rf": {
                "n_estimators": (lambda x: int(np.round(x)), n_estimators_choices),
                "min_samples_split": (
                    lambda x: int(np.round(x)),
                    min_samples_split_choices,
                ),
                "min_samples_leaf": (
                    lambda x: int(np.round(x)),
                    min_samples_leaf_choices,
                ),
            },
            "svm_rbf": {
                "gamma": (float, gamma_choices),
                "C": (float, c_choices),
            },
            "svm_linear": {
                "C": (float, c_choices),
            },
            "nnet": {
                "hidden_layer_sizes": (
                    lambda x: (int(np.round(x)),),
                    hidden_layer_size_choices,
                )
            },
        }

        ncep_choices = hp.uniform("ncep", 13, 48)
        fmin_choices = hp.uniform("fmin", 0, 5)
        fmax_choices = hp.uniform("fmax", 8, 24)
        mfcc_params = {
            "mfcc:ncep": (lambda x: int(np.round(x)), ncep_choices),
            "mfcc:fmin": (lambda x: int(np.round(x) * 100), fmin_choices),
            "mfcc:fmax": (lambda x: int(np.round(x) * 1000), fmax_choices),
        }

        space = []
        for arg_name, (converter, arg_values) in choices[clsf_type].items():
            space.append(arg_values)
            params_names.append(arg_name)
            params_converters.append(converter)
            params_count += 1

        for arg_name, (converter, arg_values) in mfcc_params.items():
            space.append(arg_values)
            params_names.append(arg_name)
            params_converters.append(converter)
            params_count += 1

        trials = Trials()
        best = fmin(fn=loss, space=space, algo=tpe.suggest, max_evals=20, trials=trials)
        print(best)

        with open(trials_file, "wb") as f:
            pickle.dump(trials, f)

        best_trial = trials.best_trial
        best_trial_args_values_ = best_trial["misc"]["vals"]
        best_trial_args_values = {}
        for arg_name, arg_values in best_trial_args_values_.items():
            if arg_name in choices[clsf_type]:
                converter = choices[clsf_type][arg_name][0]
            else:
                converter = mfcc_params["mfcc:" + arg_name][0]
            arg_value = converter(arg_values[0])
            best_trial_args_values[arg_name] = arg_value

        model_args = ["id"] + list(best_trial_args_values.keys()) + ["accuracy"]

        model_args_values = {x: [] for x in model_args}
        for idx, trial in enumerate(trials.trials):
            if trial == best_trial:
                idx = "Best"
            trial_args_values = trial["misc"]["vals"]
            for arg_name in model_args:
                if arg_name == "id":
                    model_args_values["id"].append(idx)
                elif arg_name == "accuracy":
                    trial_accuracy = 1.0 - trial["result"]["loss"]
                    model_args_values["accuracy"].append(trial_accuracy)
                else:
                    if arg_name in choices[clsf_type]:
                        converter = choices[clsf_type][arg_name][0]
                    else:
                        converter = mfcc_params["mfcc:" + arg_name][0]
                    val = converter(trial_args_values[arg_name][0])
                    # val = choice[choice_idx]
                    model_args_values[arg_name].append(val)

        with open(tsv_file, variables["open_mode"], encoding="utf-8") as f:
            for arg in model_args:
                values = model_args_values[arg]
                f.write("{}\t".format(arg))
                f.write("\t".join(map(str, values)))
                f.write("\n")
            variables["open_mode"] = "a"
