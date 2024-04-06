import pickle

from django.core.management.base import BaseCommand

import numpy as np
from hyperopt import Trials, fmin, hp, tpe
from scipy.stats import zscore

from koe.management.commands.lstm import exclude_no_labels, get_labels_by_sids
from koe.ml.nd_vl_s2s_autoencoder import NDS2SAEFactory
from koe.ml.s2senc_utils import encode_syllables, read_variables
from koe.ml_utils import classifiers, get_ratios
from koe.model_utils import get_or_error
from koe.models import AudioFile, Database, Segment
from koe.rnn_models import EnumDataProvider
from koe.spect_utils import extractors, load_global_min_max
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


def encode_into_data(variables, encoder, session, database_name, kernel_only):
    database = get_or_error(Database, dict(name__iexact=database_name))
    audio_files = AudioFile.objects.filter(database=database)
    segments = Segment.objects.filter(audio_file__in=audio_files)

    encoding_result = encode_syllables(variables, encoder, session, segments, kernel_only)
    features_value = np.array(list(encoding_result.values()))
    sids = np.array(list(encoding_result.keys()), dtype=np.int32)

    sid_sorted_inds = np.argsort(sids)
    sids = sids[sid_sorted_inds]
    features_value = features_value[sid_sorted_inds]
    features_value = features_value.astype(np.float32)

    return sids, features_value


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

        parser.add_argument("--load-from", action="store", dest="load_from", required=True, type=str)

        parser.add_argument("--format", action="store", dest="format", default="spect", type=str)

        parser.add_argument("--denormalised", action="store_true", dest="denormalised", default=False)

        parser.add_argument("--min-max-loc", action="store", dest="min_max_loc", default=False)

        parser.add_argument("--kernel-only", action="store_true", dest="kernel_only", default=False)

        parser.add_argument(
            "--ratio",
            action="store",
            dest="ratio",
            required=False,
            default="80:10:10",
            type=str,
        )

        parser.add_argument("--profile", dest="profile", action="store", required=False)

    def handle(self, *args, **options):
        clsf_type = options["clsf_type"]
        database_name = options["database_name"]
        annotator_name = options["annotator_name"]
        label_level = options["label_level"]
        min_occur = options["min_occur"]
        ipc = options["ipc"]
        ratio_ = options["ratio"]
        profile = options["profile"]

        load_from = options["load_from"]
        format = options["format"]
        min_max_loc = options["min_max_loc"]
        denormalised = options["denormalised"]
        kernel_only = options["kernel_only"]

        extractor = extractors[format]

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

        open_mode = "w"

        assert clsf_type in classifiers.keys(), "Unknown _classify: {}".format(clsf_type)
        classifier = classifiers[clsf_type]

        annotator = get_or_error(User, dict(username__iexact=annotator_name))

        if not load_from.lower().endswith(".zip"):
            load_from += ".zip"

        variables = read_variables(load_from)
        variables["extractor"] = extractor
        variables["denormalised"] = denormalised

        if denormalised:
            global_min, global_max = load_global_min_max(min_max_loc)
            variables["global_min"] = global_min
            variables["global_max"] = global_max

        variables["is_log_psd"] = format.startswith("log_")

        factory = NDS2SAEFactory()
        factory.set_output(load_from)
        factory.learning_rate = None
        factory.learning_rate_func = None
        encoder = factory.build()
        session = encoder.recreate_session()

        _sids, full_data = encode_into_data(variables, encoder, session, database_name, kernel_only)

        labels, no_label_ids = get_labels_by_sids(_sids, label_level, annotator, min_occur)

        if len(no_label_ids) > 0:
            sids, _, labels = exclude_no_labels(_sids, None, labels, no_label_ids)
            lookup_ids_rows = np.searchsorted(_sids, sids)
            full_data = full_data[lookup_ids_rows, :]

        full_data = zscore(full_data)
        full_data[np.where(np.isnan(full_data))] = 0
        full_data[np.where(np.isinf(full_data))] = 0

        ndims = full_data.shape[1]

        unique_labels = np.unique(labels)
        nlabels = len(unique_labels)

        dp = EnumDataProvider(full_data, labels, balanced=True)
        trainvalidset, testset = dp.split(test_ratio, limits=(ipc_min, ipc_max))

        v2t_ratio = valid_ratio / (train_ratio + valid_ratio)
        nfolds = int(np.floor(1.0 / v2t_ratio + 0.01))

        params_names = []
        params_converters = []
        params_count = 0

        def loss(params):
            classifier_args = {}
            for i in range(params_count):
                param_name = params_names[i]
                param_converter = params_converters[i]
                param_value = params[i]
                classifier_args[param_name] = param_converter(param_value)

            print(classifier_args)
            score = perform_k_fold(classifier, trainvalidset, nfolds, v2t_ratio, nlabels, **classifier_args)
            return 1.0 - score

        n_estimators_choices = hp.uniform("n_estimators", 40, 100)
        min_samples_split_choices = hp.uniform("min_samples_split", 2, 21)
        min_samples_leaf_choices = hp.uniform("min_samples_leaf", 1, 20)

        n_features = full_data.shape[1]
        auto_gamma = 1 / n_features
        gamma_choices = hp.uniform("gamma", auto_gamma / 10, auto_gamma * 10)
        c_choices = hp.uniform("C", -1, 2)
        hidden_layer_size_choices = hp.uniform("hidden_layer_sizes", 100, 5000)
        n_neighbors_choices = hp.uniform("n_neighbors", 1, 10)

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
                "C": (lambda x: 10**x, c_choices),
            },
            "svm_linear": {
                "C": (lambda x: 10**x, c_choices),
            },
            "nnet": {
                "hidden_layer_sizes": (
                    lambda x: (int(np.round(x)),),
                    hidden_layer_size_choices,
                )
            },
            "knn": {"n_neighbors": (lambda x: int(np.round(x)), n_neighbors_choices)},
        }

        space = []
        for arg_name, (converter, arg_values) in choices[clsf_type].items():
            space.append(arg_values)
            params_names.append(arg_name)
            params_converters.append(converter)
            params_count += 1

        trials = Trials()
        max_evals = params_count * 10
        best = fmin(fn=loss, space=space, algo=tpe.suggest, max_evals=max_evals, trials=trials)
        print(best)

        with open(trials_file, "wb") as f:
            pickle.dump(trials, f)

        best_trial = trials.best_trial
        best_trial_args_values_ = best_trial["misc"]["vals"]
        best_trial_args_values = {}
        for arg_name, arg_values in best_trial_args_values_.items():
            converter = choices[clsf_type][arg_name][0]
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
                    # choice = choices[clsf_type][arg_name]
                    converter = choices[clsf_type][arg_name][0]
                    val = converter(trial_args_values[arg_name][0])
                    # val = choice[choice_idx]
                    model_args_values[arg_name].append(val)

        # Perform classification on the test set
        train_x = np.array(trainvalidset.data)
        train_y = np.array(trainvalidset.labels, dtype=np.int32)
        test_x = np.array(testset.data)
        test_y = np.array(testset.labels, dtype=np.int32)

        score, label_hits, label_misses, cfmat, importances = classifier(
            train_x, train_y, test_x, test_y, nlabels, True, **best_trial_args_values
        )
        lb_hitrates = label_hits / (label_hits + label_misses).astype(np.float)

        with open(tsv_file, open_mode, encoding="utf-8") as f:
            for arg in model_args:
                values = model_args_values[arg]
                f.write("{}\t".format(arg))
                f.write("\t".join(map(str, values)))
                f.write("\n")

            f.write("Results using best-model's paramaters on testset\n")
            f.write("Feature group\tNdims\tLabel prediction score\t{}\n".format("\t ".join(unique_labels)))
            f.write("{}\t{}\t{}\t{}\n".format("s2senc", ndims, score, "\t".join(map(str, lb_hitrates))))

            f.write("\n")
            open_mode = "a"
