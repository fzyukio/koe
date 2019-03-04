import os
import pickle

import numpy as np
from django.core.management.base import BaseCommand
from hyperopt import Trials
from hyperopt import fmin, tpe, hp
from scipy.stats import zscore

from koe.aggregator import aggregator_map
from koe.management.commands.extract_mfcc_multiparams import extract_mfcc_multiparams
from koe.management.commands.lstm import get_labels_by_sids, exclude_no_labels
from koe.ml_utils import classifiers, get_ratios
from koe.model_utils import get_or_error
from koe.models import Database, Aggregation
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

        score, label_hits, label_misses, importances =\
            classifier(train_x, train_y, valid_x, valid_y, nlabels, **classifier_args)
        scores.append(score)
    return np.mean(scores)


converters = {
    'svm_rbf': {
        'C': lambda x: 10 ** float(x),
        'gamma': lambda x: float(x)
    },
    'svm_linear': {
        'C': lambda x: 10 ** float(x),
    },
    'nnet': {
        'hidden_layer_sizes': lambda x: (x, )
    },
    'rf': {
        'n_estimators': lambda x: x,
        'min_samples_split': lambda x: x,
        'min_samples_leaf': lambda x: x,
    },
}


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

        parser.add_argument('--load-dir', dest='load_dir', action='store', required=True)

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
        profile = options.get('profile', None)
        load_dir = options['load_dir']

        tsv_file = profile + '.tsv'
        trials_file = profile + '.trials'

        if ipc is not None:
            assert ipc <= min_occur, 'Instances per class cannot exceed as min-occur'
            ipc_min = ipc
            ipc_max = ipc
        else:
            ipc_min = min_occur
            ipc_max = int(np.floor(min_occur * 1.5))

        train_ratio, valid_ratio = get_ratios(ratio_, 2)

        open_mode = 'w'

        assert clsf_type in classifiers.keys(), 'Unknown _classify: {}'.format(clsf_type)
        classifier = classifiers[clsf_type]

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        aggregations = Aggregation.objects.filter(enabled=True).order_by('id')
        aggregators = [aggregator_map[x.name] for x in aggregations]

        _sids, _tids = get_sids_tids(database)
        _labels, no_label_ids = get_labels_by_sids(_sids, label_level, annotator, min_occur)
        if len(no_label_ids) > 0:
            _sids, _tids, _labels = exclude_no_labels(_sids, _tids, _labels, no_label_ids)

        unique_labels, enum_labels = np.unique(_labels, return_inverse=True)
        fold = split_classwise(enum_labels, ratio=valid_ratio, limits=(min_occur, int(np.floor(min_occur * 1.5))),
                               nfolds=1, balanced=True)
        train = fold[0]['train']
        test = fold[0]['test']
        all_indices = np.concatenate((train, test))

        sids = _sids[all_indices]
        tids = _tids[all_indices]
        labels = _labels[all_indices]

        with open('/tmp/hyperopt.pkl', 'rb') as f:
            saved = pickle.load(f)

        performance_data = saved[clsf_type]
        accuracies = performance_data['accuracies']
        groups = performance_data['groups']
        params = performance_data['params']

        group_name = '{}-{}'.format('mfcc', source)
        group_member_inds = np.where(groups == group_name)
        group_accuracies = accuracies[group_member_inds]

        best_acc_idx = np.argmax(group_accuracies)

        group_params = {}
        best_params = {}
        for param_name in params:
            param_values = np.array(params[param_name])
            group_param_values = param_values[group_member_inds]
            group_params[param_name] = group_param_values

            converter = converters[clsf_type][param_name]
            best_params[param_name] = converter(group_param_values[best_acc_idx])

        params_names = []
        params_converters = []
        params_count = 0

        v2t_ratio = valid_ratio / (train_ratio + valid_ratio)
        nfolds = int(np.floor(1. / v2t_ratio + 0.01))

        def loss(params):
            mfcc_args = {}
            for i in range(params_count):
                param_name = params_names[i]
                param_converter = params_converters[i]
                param_value = params[i]
                mfcc_args[param_name] = param_converter(param_value)

            _fmin = mfcc_args['fmin']
            _fmax = mfcc_args['fmax']
            _ncep = mfcc_args['ncep']

            extract_mfcc_multiparams(database_name, load_dir, _ncep, _fmin, _fmax)

            data = []
            tid2rows = {tid: [] for tid in tids}

            for aggregator in aggregators:
                agg_saved_file = 'database={}-feature=mfcc-aggregator={}-fmin={}-fmax={}-ncep={}.pkl'\
                    .format(database_name, aggregator.get_name(), _fmin, _fmax, _ncep)
                agg_saved_file_loc = os.path.join(load_dir, agg_saved_file)

                with open(agg_saved_file_loc, 'rb') as f:
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
            trainvalidset, _ = dp.split(0, limits=(ipc_min, ipc_max))

            score = perform_k_fold(classifier, trainvalidset, nfolds, v2t_ratio, nlabels, **best_params)
            return 1. - score

        ncep_choices = hp.uniform('ncep', 13, 48)
        fmin_choices = hp.uniform('fmin', 0, 5)
        fmax_choices = hp.uniform('fmax', 8, 24)
        mfcc_params = {
            'ncep': (lambda x: int(np.round(x)), ncep_choices),
            'fmin': (lambda x: int(np.round(x) * 100), fmin_choices),
            'fmax': (lambda x: int(np.round(x) * 1000), fmax_choices),
        }

        space = []

        for arg_name, (converter, arg_values) in mfcc_params.items():
            space.append(arg_values)
            params_names.append(arg_name)
            params_converters.append(converter)
            params_count += 1

        trials = Trials()
        best = fmin(fn=loss, space=space, algo=tpe.suggest, max_evals=100, trials=trials)
        print(best)

        with open(trials_file, 'wb') as f:
            pickle.dump(trials, f)

        best_trial = trials.best_trial
        best_trial_args_values_ = best_trial['misc']['vals']
        best_trial_args_values = {}
        for arg_name, arg_values in best_trial_args_values_.items():
            converter = mfcc_params[arg_name][0]
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
                    converter = mfcc_params[arg_name][0]
                    val = converter(trial_args_values[arg_name][0])
                    model_args_values[arg_name].append(val)

        with open(tsv_file, open_mode, encoding='utf-8') as f:
            for arg in model_args:
                values = model_args_values[arg]
                f.write('{}\t'.format(arg))
                f.write('\t'.join(map(str, values)))
                f.write('\n')
            open_mode = 'a'
