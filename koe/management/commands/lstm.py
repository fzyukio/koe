r"""
Train a LSTM on audio segments.
"""

import numpy as np
from django.core.management.base import BaseCommand
from pymlfunc import tictoc

from koe import binstorage3 as bs
from koe.features.feature_extract import feature_map, feature_whereabout
from koe.model_utils import get_labels_by_sids, exclude_no_labels
from koe.model_utils import get_or_error
from koe.models import Database, Feature
from koe.rnn_models import OneHotSequenceProvider
from koe.rnn_train import train
from koe.storage_utils import get_sids_tids, get_storage_loc_template
from root.models import User

feature_whereabout = {x.__name__[len('koe.features.'):]: y for x, y in feature_whereabout.items()}
ftgroup_names = list(feature_whereabout.keys())

feature_whereabout_flat = [x for group in feature_whereabout.values() for x in group]


def extract_rawdata(ids, features):
    storage_loc_template = get_storage_loc_template()
    data_by_id = {id: [] for id in ids}

    for feature in features:
        storage_loc = storage_loc_template.format(feature.name)
        with tictoc('{}'.format(feature.name)):
            feature_values = bs.retrieve(ids, storage_loc)
            for id, feature_value in zip(ids, feature_values):
                data_by_id[id].append(feature_value)

    data = []
    for id in ids:
        feature_values = data_by_id[id]
        data.append(feature_values)

    return data


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--annotator-name', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who owns this database, case insensitive', )

        # parser.add_argument('--population', action='store', dest='population_name', required=True, type=str,
        #                     help='Prefix of song name to identify population - e.g LBI, PKI', )

        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )

        parser.add_argument('--min-occur', action='store', dest='min_occur', default=2, type=int,
                            help='Ignore syllable classes that have less than this number of instances', )

        # parser.add_argument('--feature-group', action='store', dest='feature_group', default=None, type=str,
        #                     help='Comma-separated feature IDs', )

        parser.add_argument('--to-csv', dest='csv_filename', action='store', required=False)

        parser.add_argument('--no-gpu', dest='no_gpu', action='store_true', default=False)

    def handle(self, *args, **options):
        database_name = options['database_name']
        annotator_name = options['annotator_name']
        # population_name = options['population_name']
        label_level = options['label_level']
        min_occur = options['min_occur']
        no_gpu = options['no_gpu']
        # feature_group = options['feature_group']

        # if feature_group:
        #     feature_names = feature_names.split(',')
        #     features = Feature.objects.filter(name__in=feature_names).order_by('id')
        # else:
        #     features = Feature.objects.all().order_by('id')
        #
        # features = features.exclude(is_fixed_length=True)

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))

        features = Feature.objects.all().order_by('id')
        # features = list(features)[:4]

        enabled_features = []
        for f in features:
            if f.name in feature_map:
                enabled_features.append(f)

        sids, tids = get_sids_tids(database)
        labels, no_label_ids = get_labels_by_sids(sids, label_level, annotator, min_occur)

        if len(no_label_ids) > 0:
            sids, tids, labels = exclude_no_labels(sids, tids, labels, no_label_ids)

        full_data = extract_rawdata(tids, enabled_features)
        feature_inds = {x.name: idx for idx, x in enumerate(enabled_features)}

        for ftgroup_name in ftgroup_names + ['all']:
            data = []
            if ftgroup_name == 'all':
                features = feature_whereabout_flat
            else:
                features = feature_whereabout[ftgroup_name]
            ftgroup_col_inds = []
            for feature_name, is_fixed_length, _ in features:
                col_name = feature_name
                feature_ind = feature_inds.get(col_name, None)
                if feature_ind is not None:
                    ftgroup_col_inds.append(feature_ind)

            for full_row, sid in zip(full_data, sids):
                row = [full_row[x] for x in ftgroup_col_inds]
                try:
                    row = np.vstack(row).T
                except ValueError:
                    print('Encounter error at id={}'.format(sid))
                    for idx, (feature_name, is_fixed_length, _) in enumerate(features):
                        print('{} - {}'.format(feature_name, row[idx].shape))
                data.append(row)

            data_provider = OneHotSequenceProvider(data, labels, balanced=True)
            model_name = '{}_{}_{}'.format(database_name, label_level, ftgroup_name)
            print('Training for: {}'.format(model_name))
            train(data_provider, name=model_name, disable_gpu=no_gpu)
