import json
import pickle

import numpy as np
from django.core.management.base import BaseCommand
from hyperopt import Trials
from hyperopt import fmin, tpe, hp
from scipy.stats import zscore

from koe.aggregator import aggregator_map
from koe.feature_utils import pca_optimal
from koe.features.feature_extract import feature_map, ftgroup_names
from koe.management.commands.lstm import get_labels_by_sids, exclude_no_labels
from koe.ml_utils import classifiers, get_ratios
from koe.model_utils import get_or_error
from koe.models import Database, DataMatrix, Feature, Aggregation
from koe.rnn_models import EnumDataProvider
from koe.storage_utils import get_tids
from koe.ts_utils import bytes_to_ndarray
from koe.ts_utils import get_rawdata_from_binary
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

        score, label_hits, label_misses, importances =\
            classifier(train_x, train_y, valid_x, valid_y, nlabels, **classifier_args)
        scores.append(score)
    return np.mean(scores)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--classifier', action='store', dest='clsf_type', required=True, type=str,
                            help='Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda', )

        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--source', action='store', dest='source', required=True, type=str,
                            help='Can be full, pca', )

        parser.add_argument('--annotator-name', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who owns this database, case insensitive', )

        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )

        parser.add_argument('--min-occur', action='store', dest='min_occur', default=2, type=int,
                            help='Ignore syllable classes that have less than this number of instances', )

        parser.add_argument('--ipc', action='store', dest='ipc', default=None, type=int,
                            help='Use this value as number of instances per class. Must be <= min-occur', )

        parser.add_argument('--ratio', action='store', dest='ratio', required=False, default='80:10:10', type=str)

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=10, type=int)

        parser.add_argument('--profile', dest='profile', action='store', required=False)

        parser.add_argument('--dm-name', dest='dm_name', action='store', required=False)

    def handle(self, *args, **options):
        clsf_type = options['clsf_type']
        database_name = options['database_name']
        source = options['source']
        annotator_name = options['annotator_name']
        label_level = options['label_level']
        min_occur = options['min_occur']
        ipc = options['ipc']
        ratio_ = options['ratio']
        niters = options['niters']
        profile = options['profile']
        dm_name = options['dm_name']

        tsv_file = profile + '.tsv'
        trials_file = profile + '.trials'
        if ipc is not None:
            assert ipc <= min_occur, 'Instances per class cannot exceed as min-occur'
            ipc_min = ipc
            ipc_max = ipc
        else:
            ipc_min = min_occur
            ipc_max = int(np.floor(min_occur * 1.5))

        train_ratio, valid_ratio, test_ratio = get_ratios(ratio_)

        open_mode = 'w'

        assert clsf_type in classifiers.keys(), 'Unknown _classify: {}'.format(clsf_type)
        classifier = classifiers[clsf_type]

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))

        if dm_name is None:
            features = Feature.objects.all().order_by('id')
            aggregations = Aggregation.objects.filter(enabled=True).order_by('id')
            aggregators = [aggregator_map[x.name] for x in aggregations]

            enabled_features = []
            for f in features:
                if f.name in feature_map:
                    enabled_features.append(f)

            features_hash = '-'.join(list(map(str, [x.id for x in enabled_features])))
            aggregations_hash = '-'.join(list(map(str, aggregations.values_list('id', flat=True))))

            dm = DataMatrix.objects.filter(database=database, features_hash=features_hash,
                                           aggregations_hash=aggregations_hash).last()
            if dm is None:
                raise Exception('No full data matrix for database {}'.format(database_name))
        else:
            dm = DataMatrix.objects.filter(database=database, name=dm_name).first()
            if dm is None:
                raise Exception('No such matrix {} for database {}'.format(dm_name, database_name))

            if dm.aggregations_hash:
                aggregations_list = dm.aggregations_hash.split('-')
                aggregators = [aggregator_map[x] for x in aggregations_list]
            else:
                aggregators = []


            ftgroup_names = {
                'custom': dm.features_hash.split('-')
            }

        dm_sids_path = dm.get_sids_path()
        dm_tids_path = dm.get_tids_path()
        dm_bytes_path = dm.get_bytes_path()
        feature_cols = dm.get_cols_path()
        with open(feature_cols, 'r', encoding='utf-8') as f:
            col_inds = json.load(f)

        _sids = bytes_to_ndarray(dm_sids_path, np.int32)
        _sids, sort_order = np.unique(_sids, return_index=True)

        try:
            _tids = bytes_to_ndarray(dm_tids_path, np.int32)
            _tids = _tids[sort_order]
        except FileNotFoundError:
            _tids = get_tids(database, _sids)

        full_data = get_rawdata_from_binary(dm_bytes_path, len(_sids))
        full_data = full_data[sort_order, :]

        labels, no_label_ids = get_labels_by_sids(_sids, label_level, annotator, min_occur)

        if len(no_label_ids) > 0:
            sids, tids, labels = exclude_no_labels(_sids, _tids, labels, no_label_ids)
            lookup_ids_rows = np.searchsorted(_sids, sids)
            full_data = full_data[lookup_ids_rows, :]

        full_data = zscore(full_data)
        full_data[np.where(np.isnan(full_data))] = 0
        full_data[np.where(np.isinf(full_data))] = 0

        unique_labels = np.unique(labels)
        nlabels = len(unique_labels)

        for ftgroup_name, feature_names in ftgroup_names.items():
            if ftgroup_name == 'all':
                features = list(feature_map.values())
            else:
                features = [feature_map[x] for x in feature_names]
            ft_col_inds = []
            for feature in features:
                if feature.is_fixed_length:
                    col_name = feature.name
                    col_range = col_inds[col_name]
                    ft_col_inds += range(col_range[0], col_range[1])
                else:
                    for aggregator in aggregators:
                        col_name = '{}_{}'.format(feature.name, aggregator.get_name())
                        col_range = col_inds[col_name]
                        ft_col_inds += range(col_range[0], col_range[1])

            ft_col_inds = np.array(ft_col_inds, dtype=np.int32)
            ndims = len(ft_col_inds)
            data = full_data[:, ft_col_inds]

            if source == 'pca':
                explained, data = pca_optimal(data, ndims, 0.9)
                pca_dims = data.shape[1]

            dp = EnumDataProvider(data, labels, balanced=True)
            trainvalidset, testset = dp.split(test_ratio, limits=(min_occur, int(np.floor(min_occur * 1.5))))

            v2t_ratio = valid_ratio / (train_ratio + valid_ratio)
            nfolds = int(np.floor(1. / v2t_ratio + 0.01))

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
                return 1. - score

            n_estimators_choices = hp.uniform('n_estimators', 40, 100)
            min_samples_split_choices = hp.uniform('min_samples_split', 2, 21)
            min_samples_leaf_choices = hp.uniform('min_samples_leaf', 1, 20)

            n_features = data.shape[1]
            auto_gamma = 1 / n_features
            gamma_choices = hp.uniform('gamma', auto_gamma / 10, auto_gamma * 10)
            c_choices = hp.uniform('C', -1, 2)
            hidden_layer_size_choices = hp.uniform('hidden_layer_sizes', 100, 5000)

            choices = {
                'rf': {
                    'n_estimators': (lambda x: int(np.round(x)), n_estimators_choices),
                    'min_samples_split': (lambda x: int(np.round(x)), min_samples_split_choices),
                    'min_samples_leaf': (lambda x: int(np.round(x)), min_samples_leaf_choices),
                },
                'svm_rbf': {
                    'gamma': (float, gamma_choices),
                    'C': (lambda x: 10 ** x, c_choices),
                },
                'svm_linear': {
                    'C': (lambda x: 10 ** x, c_choices),
                },
                'nnet': {
                    'hidden_layer_sizes': (lambda x: (int(np.round(x)),), hidden_layer_size_choices)
                }
            }

            space = []
            for arg_name, (converter, arg_values) in choices[clsf_type].items():
                space.append(arg_values)
                params_names.append(arg_name)
                params_converters.append(converter)
                params_count += 1

            trials = Trials()
            max_evals = params_count * 30
            best = fmin(fn=loss, space=space, algo=tpe.suggest, max_evals=max_evals, trials=trials)
            print(best)

            with open(trials_file, 'wb') as f:
                pickle.dump(trials, f)

            best_trial = trials.best_trial
            best_trial_args_values_ = best_trial['misc']['vals']
            best_trial_args_values = {}
            for arg_name, arg_values in best_trial_args_values_.items():
                converter = choices[clsf_type][arg_name][0]
                arg_value = converter(arg_values[0])
                best_trial_args_values[arg_name] = arg_value

            model_args = ['id'] + list(best_trial_args_values.keys()) + ['accuracy']

            model_args_values = {x: [] for x in model_args}
            for idx, trial in enumerate(trials.trials):
                if trial == best_trial:
                    idx = 'Best'
                trial_args_values = trial['misc']['vals']
                for arg_name in model_args:
                    if arg_name == 'id':
                        model_args_values['id'].append(idx)
                    elif arg_name == 'accuracy':
                        trial_accuracy = 1. - trial['result']['loss']
                        model_args_values['accuracy'].append(trial_accuracy)
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

            score, label_hits, label_misses, cfmat, importances =\
                classifier(train_x, train_y, test_x, test_y, nlabels, True, **best_trial_args_values)
            lb_hitrates = label_hits / (label_hits + label_misses).astype(np.float)

            with open(tsv_file, open_mode, encoding='utf-8') as f:
                for arg in model_args:
                    values = model_args_values[arg]
                    f.write('{}\t'.format(arg))
                    f.write('\t'.join(map(str, values)))
                    f.write('\n')

                f.write('Results using best-model\'s paramaters on testset\n')

                if source == 'full':
                    f.write('Feature group\tNdims\tLabel prediction score\t{}\n'
                            .format('\t '.join(unique_labels)))
                    f.write('{}\t{}\t{}\t{}\n'
                            .format(ftgroup_name, ndims, score, '\t'.join(map(str, lb_hitrates))))
                else:
                    f.write('Feature group\tNdims\tPCA explained\tPCA Dims\tLabel prediction score\t{}\n'
                            .format('\t '.join(unique_labels)))
                    f.write('{}\t{}\t{}\t{}\t{}\t{}\n'
                            .format(ftgroup_name, ndims, explained, pca_dims, score, '\t'.join(map(str, lb_hitrates))))
                f.write('\n')
                open_mode = 'a'
