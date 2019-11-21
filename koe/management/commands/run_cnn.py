import numpy as np
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.management.commands.lstm import get_labels_by_sids, exclude_no_labels, extract_rawdata
from koe.ml_utils import get_ratios, cnn
from koe.model_utils import get_or_error
from koe.models import Database, Feature
from koe.rnn_models import OneHotSequenceProvider
from koe.storage_utils import get_sids_tids
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
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--annotator-name', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who owns this database, case insensitive', )

        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )

        parser.add_argument('--min-occur', action='store', dest='min_occur', default=10, type=int,
                            help='Ignore syllable classes that have less than this number of instances', )

        parser.add_argument('--ipc', action='store', dest='ipc', default=None, type=int,
                            help='Use this value as number of instances per class. Must be <= min-occur', )

        parser.add_argument('--ratio', action='store', dest='ratio', required=False, default='80:10:10', type=str)

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=10, type=int)

        parser.add_argument('--profile', dest='profile', action='store', required=False)

    def handle(self, *args, **options):
        database_name = options['database_name']
        annotator_name = options['annotator_name']
        label_level = options['label_level']
        min_occur = options['min_occur']
        ipc = options['ipc']
        ratio_ = options['ratio']
        niters = options['niters']
        profile = options.get('profile', None)
        tsv_file = profile + '.tsv'

        if ipc is not None:
            assert ipc <= min_occur, 'Instances per class cannot exceed as min-occur'
            ipc_min = ipc
            ipc_max = ipc
        else:
            ipc_min = min_occur
            ipc_max = int(np.floor(min_occur * 1.5))

        train_ratio, valid_ratio, test_ratio = get_ratios(ratio_)

        open_mode = 'w'

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        features = Feature.objects.all().order_by('id').filter(name='spectrum')

        sids, tids = get_sids_tids(database)
        labels, no_label_ids = get_labels_by_sids(sids, label_level, annotator, min_occur)

        if len(no_label_ids) > 0:
            sids, tids, labels = exclude_no_labels(sids, tids, labels, no_label_ids)

        full_data = extract_rawdata(tids, features)
        data = [x[0].T for x in full_data]

        unique_labels = np.unique(labels)
        nlabels = len(unique_labels)

        dp = OneHotSequenceProvider(data, labels, balanced=True)
        trainvalidset, testset = dp.split(test_ratio, limits=(min_occur, int(np.floor(min_occur * 1.5))))

        v2t_ratio = valid_ratio / (train_ratio + valid_ratio)
        nfolds = int(np.floor(1. / v2t_ratio + 0.01))

        hidden_layer_sizes_choices = [
            (100, ), (200, ), (400, ),
            (100, 100), (100, 200), (100, 400),
            (200, 100), (200, 200), (200, 400),
            (400, 100), (400, 200), (400, 400),
        ]

        choices = {
            'cnn': {
                'hidden_layer_sizes': hidden_layer_sizes_choices
            }
        }

        best_trial_args_values = {}

        for arg_name, arg_values in choices['cnn'].items():
            losses = []
            ids = []

            def loss_func(params):
                arg_value = params[0]
                classifier_args = best_trial_args_values.copy()
                classifier_args[arg_name] = arg_value
                print('classifier_args = {}'.format(classifier_args))
                score = perform_k_fold(cnn, trainvalidset, nfolds, v2t_ratio, nlabels, **classifier_args)
                return 1. - score

            for idx, arg_value in enumerate(arg_values):
                loss = loss_func((arg_value, ))
                ids.append(idx)
                losses.append(loss)

            best_loss_idx = np.argmin(losses)
            best_arg_value = arg_values[best_loss_idx]
            best_trial_args_values[arg_name] = best_arg_value

            model_args = ['id'] + list(best_trial_args_values.keys()) + ['accuracy']

            model_args_values = {x: [] for x in model_args}
            for idx, loss in enumerate(losses):
                if idx == best_loss_idx:
                    idx_str = 'Best'
                else:
                    idx_str = str(idx)
                # trial_args_values = trial['misc']['vals']
                for arg_name_ in model_args:
                    if arg_name_ == 'id':
                        model_args_values['id'].append(idx_str)
                    elif arg_name_ == 'accuracy':
                        trial_accuracy = 1. - loss
                        model_args_values['accuracy'].append(trial_accuracy)
                    else:
                        if arg_name_ == arg_name:
                            val = arg_values[idx]
                        else:
                            val = best_trial_args_values[arg_name_]
                        model_args_values[arg_name_].append(val)

            with open(tsv_file, open_mode, encoding='utf-8') as f:
                for arg in model_args:
                    values = model_args_values[arg]
                    f.write('{}\t'.format(arg))
                    f.write('\t'.join(map(str, values)))
                    f.write('\n')
                open_mode = 'a'

        # Perform classification on the test set
        nfolds = int(np.floor(1 / test_ratio + 0.01))
        ntrials = nfolds * niters
        label_prediction_scores = [0] * ntrials
        label_hitss = [0] * ntrials
        label_missess = [0] * ntrials
        label_hitrates = np.empty((ntrials, nlabels))
        label_hitrates[:] = np.nan
        importancess = np.empty((ntrials, data.shape[1]))
        cfmats = np.ndarray((ntrials, nlabels, nlabels))
        ind = 0

        bar = Bar('Running CNN', max=ntrials)

        for iter in range(niters):
            traintetset, _ = dp.split(0, limits=(ipc_min, ipc_max))
            traintetset.make_folds(nfolds, test_ratio)

            for k in range(nfolds):
                trainset, testset = traintetset.get_fold(k)
                train_x = np.array(trainset.data)
                train_y = np.array(trainset.labels, dtype=np.int32)
                test_x = np.array(testset.data)
                test_y = np.array(testset.labels, dtype=np.int32)

                score, label_hits, label_misses, cfmat, importances =\
                    cnn(train_x, train_y, test_x, test_y, nlabels, True, **best_trial_args_values)

                label_prediction_scores[ind] = score
                label_hitss[ind] = label_hits
                label_missess[ind] = label_misses

                label_hitrate = label_hits / (label_hits + label_misses).astype(np.float)

                label_hitrates[ind, :] = label_hitrate
                importancess[ind, :] = importances
                cfmats[ind, :, :] = cfmat

                bar.next()
                ind += 1
        bar.finish()

        mean_label_prediction_scores = np.nanmean(label_prediction_scores)
        std_label_prediction_scores = np.nanstd(label_prediction_scores)
        sum_cfmat = np.nansum(cfmats, axis=0)

        with open(tsv_file, open_mode, encoding='utf-8') as f:
            f.write('Results using best-model\'s paramaters on testset\n')
            f.write('Feature group\tLabel prediction mean\tstdev\t{}\n'.format('\t '.join(unique_labels)))
            f.write('{}\t{}\t{}\t{}\n'
                    .format('Spectrum', mean_label_prediction_scores, std_label_prediction_scores,
                            '\t'.join(map(str, np.nanmean(label_hitrates, 0)))))

            f.write('\t')
            f.write('\t'.join(unique_labels))
            f.write('\n')
            for i in range(nlabels):
                label = unique_labels[i]
                cfrow = sum_cfmat[:, i]
                f.write(label)
                f.write('\t')
                f.write('\t'.join(map(str, cfrow)))
                f.write('\n')
            f.write('\n')
