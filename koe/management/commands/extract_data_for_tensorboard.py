"""
Run tsne with different numbers of dimensions, svm and export result
"""
import os

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from pymlfunc import tictoc

from koe import binstorage
from koe.aggregator import aggregators_by_type
from koe.features.feature_extract import features as full_features
from koe.management.commands.run_ndim_tsne_svm import reduce_funcs
from koe.models import Segment
from koe.ts_utils import load_config, get_safe_tensors_name, ndarray_to_bytes, write_config, write_metadata
from root.models import ExtraAttrValue
from root.utils import ensure_parent_folder_exists, data_path


def extract_rawdata(f2bs, fa2bs, ids, features, aggregators):
    rawdata = []
    for feature in features:
        if feature.is_fixed_length:
            index_filename, value_filename = f2bs[feature]
            with tictoc('{}'.format(feature.name)):
                rawdata_ = binstorage.retrieve(ids, index_filename, value_filename, flat=True)
            rawdata.append(np.stack(rawdata_))
        else:
            for aggregator in aggregators:
                index_filename, value_filename = fa2bs[feature][aggregator]
                with tictoc('{} - {}'.format(feature.name, aggregator.get_name())):
                    rawdata_ = binstorage.retrieve(ids, index_filename, value_filename, flat=True)
                rawdata.append(np.stack(rawdata_))
    rawdata = np.concatenate(rawdata, axis=1)
    return rawdata


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--annotator', action='store', dest='annotator', default='superuser', type=str,
                            help='Name of the person who labels this dataset, case insensitive', )

        parser.add_argument('--config', action='store', dest='config_name', type=str, required=True,
                            help='Name of the tensorboard configuration - if exists the tensors will be appended')

        parser.add_argument('--tensors', action='store', dest='tensors_name', type=str, required=True,
                            help='Name of the tensorboard\'s tensors data - if exists a numeric appendix will be '
                                 'appended')

        parser.add_argument('--reduce-type', action='store', dest='reduce_type', default='pca', type=str)

    def handle(self, database_name, annotator, config_name, tensors_name, reduce_type, *args, **options):
        assert reduce_type in reduce_funcs.keys(), 'Unknown function: {}'.format(reduce_type)
        reduce_func = reduce_funcs[reduce_type]

        segments = Segment.objects.filter(audio_file__database__name__iexact=database_name)
        segments_info = segments.values_list('id', 'tid')

        tids = []
        sids = []
        for sid, tid in segments_info:
            tids.append(tid)
            sids.append(sid)
        tids = np.array(tids, dtype=np.int32)
        sids = np.array(sids, dtype=np.int32)

        all_aggregators = []
        for aggregators in aggregators_by_type.values():
            all_aggregators += aggregators

        # feature to binstorage's files
        f2bs = {}
        # feature+aggregation to binstorage's files
        fa2bs = {}

        for feature in full_features:
            feature_name = feature.name
            index_filename = data_path('binary/features', '{}.idx'.format(feature_name), for_url=False)
            value_filename = data_path('binary/features', '{}.val'.format(feature_name), for_url=False)
            f2bs[feature] = (index_filename, value_filename)

            if feature not in fa2bs:
                fa2bs[feature] = {}
            for aggregator in all_aggregators:
                aggregator_name = aggregator.get_name()
                folder = os.path.join('binary', 'features', feature_name)

                index_filename = data_path(folder, '{}.idx'.format(aggregator_name), for_url=False)
                value_filename = data_path(folder, '{}.val'.format(aggregator_name), for_url=False)
                fa2bs[feature][aggregator] = (index_filename, value_filename)

        rawdata = extract_rawdata(f2bs, fa2bs, tids, full_features, all_aggregators)

        sids_sort_order = np.argsort(sids)
        sids = sids[sids_sort_order]
        tids = tids[sids_sort_order]
        rawdata = rawdata[sids_sort_order]

        dim_reduce_func = reduce_func(n_components=50)
        reduced = dim_reduce_func.fit_transform(rawdata)

        data = reduced
        metadata = {sid: [str(sid)] for sid in sids}

        label_levels = ['label', 'label_family']
        headers = ['id'] + label_levels + ['gender']

        for i in range(len(label_levels)):
            label_level = label_levels[i]
            segment_to_label = \
                {x: y.lower() for x, y in
                 ExtraAttrValue.objects
                     .filter(attr__name=label_level, attr__klass=Segment.__name__, owner_id__in=sids,
                             user__username__iexact=annotator)
                     .order_by('owner_id')
                     .values_list('owner_id', 'value')
                 }

            for sid in sids:
                metadata[sid].append(segment_to_label.get(sid, ''))

        sid_to_gender = \
            {x: y.lower() for x, y in
             Segment.objects.filter(id__in=sids).order_by('id')
                 .values_list('id', 'audio_file__individual__gender')
             }

        for sid in sids:
            metadata[sid].append(sid_to_gender.get(sid, ''))

        config_file = os.path.join(settings.MEDIA_URL, 'oss_data', '{}.json'.format(config_name))
        config_file = config_file[1:]
        config = load_config(config_file)

        safe_tensors_name = get_safe_tensors_name(config, tensors_name)
        rawdata_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.bytes'.format(safe_tensors_name))
        metadata_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.tsv'.format(safe_tensors_name))

        rawdata_relative_path = rawdata_path[1:]
        metadata_relative_path = metadata_path[1:]

        ensure_parent_folder_exists(config_file)
        ensure_parent_folder_exists(rawdata_relative_path)
        ensure_parent_folder_exists(metadata_relative_path)

        ndarray_to_bytes(data, rawdata_relative_path)
        write_metadata(metadata, sids, headers, metadata_relative_path)

        # Always write config last - to make sure it's not missing anything
        write_config(config, config_file, safe_tensors_name, data.shape, rawdata_path, metadata_path)
