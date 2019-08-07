r"""
Clustering validation.
"""
import json

import numpy as np
from django.core.management.base import BaseCommand
from progress.bar import Bar
from scipy.stats import zscore

from koe.aggregator import aggregator_map, enabled_aggregators
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


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--classifier', action='store', dest='clsf_type', required=True, type=str,
                            help='Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda', )

        parser.add_argument('--database', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--source', action='store', dest='source', required=True, type=str,
                            help='Can be full, pca', )

        parser.add_argument('--annotator', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who owns this database, case insensitive', )

        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )

        parser.add_argument('--min-occur', action='store', dest='min_occur', default=2, type=int,
                            help='Ignore syllable classes that have less than this number of instances', )

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=10, type=int)

        parser.add_argument('--ratio', action='store', dest='ratio', required=False, default='80:10:10', type=str)

        parser.add_argument('--to-csv', dest='csv_filename', action='store', required=False)

    def handle(self, *args, **options):
        clsf_type = options['clsf_type']
        database_name = options['database_name']
        source = options['source']
        annotator_name = options['annotator_name']
        label_level = options['label_level']
        min_occur = options['min_occur']
        ratio_ = options['ratio']
        niters = options['niters']
        csv_filename = options.get('csv_filename', None)

        train_ratio, valid_ratio = get_ratios(ratio_, 2)

        assert clsf_type in classifiers.keys(), 'Unknown _classify: {}'.format(clsf_type)
        classifier = classifiers[clsf_type]

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))

        features = Feature.objects.all().order_by('id')
        aggregations = Aggregation.objects.filter(enabled=True).order_by('id')

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
            _tids = get_tids(_sids)

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

        if csv_filename:
            with open(csv_filename, 'w', encoding='utf-8') as f:
                if source == 'pca':
                    f.write('Feature group\tAggregators\tNdims\tPCA explained\tPCA Dims\tLabel prediction mean\tstdev'
                            '\t{}\n'.format('\t '.join(unique_labels)))
                else:
                    f.write('Feature group\tAggregators\tNdims\tLabel prediction mean\tstdev\t{}\n'
                            .format('\t '.join(unique_labels)))

        for ftgroup_name, feature_names in ftgroup_names.items():
            for agggroup_name, aggs in list(enabled_aggregators.items()) + [('all', None)]:
                if agggroup_name == 'all':
                    aggs = [aggregator_map[x.name] for x in aggregations]
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
                        for aggregator in aggs:
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

                nfolds = int(np.floor(1 / valid_ratio + 0.01))
                ntrials = nfolds * niters
                label_prediction_scores = [0] * ntrials
                label_hitss = [0] * ntrials
                label_missess = [0] * ntrials
                label_hitrates = np.empty((ntrials, nlabels))
                label_hitrates[:] = np.nan
                importancess = np.empty((ntrials, data.shape[1]))
                cfmats = np.ndarray((ntrials, nlabels, nlabels))

                ind = 0

                bar = Bar('Features: {}. Aggregator: {}. Classifier: {} Data type: {}...'
                          .format(ftgroup_name, agggroup_name, clsf_type, source), max=ntrials)

                for iter in range(niters):
                    traintetset, _ = dp.split(0, limits=(min_occur, int(np.floor(min_occur * 1.5))))
                    traintetset.make_folds(nfolds, valid_ratio)
                    for k in range(nfolds):
                        trainset, testset = traintetset.get_fold(k)
                        train_x = np.array(trainset.data)
                        train_y = np.array(trainset.labels, dtype=np.int32)
                        test_x = np.array(testset.data)
                        test_y = np.array(testset.labels, dtype=np.int32)

                        score, label_hits, label_misses, cfmat, importances = \
                            classifier(train_x, train_y, test_x, test_y, nlabels, True)

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

                if csv_filename:
                    with open(csv_filename, 'a', encoding='utf-8') as f:
                        if source == 'full':
                            f.write('{}\t{}\t{}\t{}\t{}\t{}\n'
                                    .format(ftgroup_name, agggroup_name, ndims, mean_label_prediction_scores,
                                            std_label_prediction_scores,
                                            '\t'.join(map(str, np.nanmean(label_hitrates, 0)))))
                        else:
                            f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'
                                    .format(ftgroup_name, agggroup_name, ndims, explained, pca_dims,
                                            mean_label_prediction_scores, std_label_prediction_scores,
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
                else:
                    print('{}/{}: {} by {}: mean = {} std = {}'
                          .format(ftgroup_name, agggroup_name, clsf_type, source, mean_label_prediction_scores,
                                  std_label_prediction_scores))
