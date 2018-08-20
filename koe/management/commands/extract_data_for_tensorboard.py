"""
Run tsne with different numbers of dimensions, svm and export result
"""
import json
import os
import uuid

import numpy as np
from django.core.management.base import BaseCommand
from django.urls import reverse
from pymlfunc import tictoc

from koe import binstorage
from koe.aggregator import aggregator_map
from koe.features.feature_extract import feature_map
from koe.model_utils import get_or_error
from koe.models import Segment, Feature, Aggregation, Database, FullTensorData, DerivedTensorData
from koe.ts_utils import ndarray_to_bytes, write_config
from root.models import User
from root.utils import data_path


def extract_rawdata(f2bs, fa2bs, ids, features, aggregators):
    rawdata = []
    col_inds = {}
    col_inds_start = 0

    for feature in features:
        if feature.is_fixed_length:
            index_filename, value_filename = f2bs[feature]
            with tictoc('{}'.format(feature.name)):
                rawdata_ = binstorage.retrieve(ids, index_filename, value_filename, flat=True)
                rawdata_stacked = np.stack(rawdata_)
            rawdata.append(rawdata_stacked)
            ncols = rawdata_stacked.shape[1]
            col_inds[feature.name] = (col_inds_start, col_inds_start + ncols)
            col_inds_start += ncols
        else:
            for aggregator in aggregators:
                index_filename, value_filename = fa2bs[feature][aggregator]
                with tictoc('{} - {}'.format(feature.name, aggregator.get_name())):
                    rawdata_ = binstorage.retrieve(ids, index_filename, value_filename, flat=True)
                rawdata_stacked = np.stack(rawdata_)
                rawdata.append(rawdata_stacked)
                ncols = rawdata_stacked.shape[1]
                col_inds['{}_{}'.format(feature.name, aggregator.name)] = (col_inds_start, col_inds_start + ncols)
                col_inds_start += ncols
    rawdata = np.concatenate(rawdata, axis=1)

    return rawdata, col_inds


def get_features_from_hash(hash):
    fids = list(map(int, hash.split('-')))
    feature_names = Feature.objects.filter(id__in=fids).values_list('name', flat=True)
    features = [feature_map[x] for x in feature_names]
    return features


def get_aggregators_from_hash(hash):
    aids = list(map(int, hash.split('-')))
    aggregator_names = Aggregation.objects.filter(id__in=aids).values_list('name', flat=True)
    aggregators = [aggregator_map[x] for x in aggregator_names]
    return aggregators


def get_sids_tids(database):
    segments = Segment.objects.filter(audio_file__database=database)
    segments_info = segments.values_list('id', 'tid')

    tids = []
    sids = []
    for sid, tid in segments_info:
        tids.append(tid)
        sids.append(sid)
    tids = np.array(tids, dtype=np.int32)
    sids = np.array(sids, dtype=np.int32)
    sids_sort_order = np.argsort(sids)
    sids = sids[sids_sort_order]
    tids = tids[sids_sort_order]

    return sids, tids


def extract_tensor_data(tids, feature_hash, aggregation_hash):
    features = get_features_from_hash(feature_hash)
    aggregators = get_aggregators_from_hash(aggregation_hash)

    # feature to binstorage's files
    f2bs = {}
    # feature+aggregation to binstorage's files
    fa2bs = {}

    for feature in features:
        feature_name = feature.name
        index_filename = data_path('binary/features', '{}.idx'.format(feature_name), for_url=False)
        value_filename = data_path('binary/features', '{}.val'.format(feature_name), for_url=False)
        f2bs[feature] = (index_filename, value_filename)

        if feature not in fa2bs:
            fa2bs[feature] = {}
        for aggregator in aggregators:
            aggregator_name = aggregator.get_name()
            folder = os.path.join('binary', 'features', feature_name)

            index_filename = data_path(folder, '{}.idx'.format(aggregator_name), for_url=False)
            value_filename = data_path(folder, '{}.val'.format(aggregator_name), for_url=False)
            fa2bs[feature][aggregator] = (index_filename, value_filename)

    return extract_rawdata(f2bs, fa2bs, tids, features, aggregators)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--annotator', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who labels this dataset, case insensitive', )

    def handle(self, database_name, annotator_name, *args, **options):
        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        admin = get_or_error(User, dict(username__iexact='superuser'))

        features_hash = '-'.join(list(map(str, Feature.objects.order_by('id').values_list('id', flat=True))))
        aggregations_hash = '-'.join(
            list(map(str, Aggregation.objects.order_by('id').values_list('id', flat=True))))

        existing_tensor = DerivedTensorData.objects.filter(database=database, annotator=annotator,
                                                           features_hash=features_hash,
                                                           aggregations_hash=aggregations_hash,
                                                           dimreduce='none').first()
        if existing_tensor:
            return

        full_tensors_name = uuid.uuid4().hex
        derived_tensors_name = uuid.uuid4().hex

        full_tensor = FullTensorData(name=full_tensors_name, database=database, features_hash=features_hash,
                                     aggregations_hash=aggregations_hash)

        full_ids_path = full_tensor.get_ids_path()
        full_bytes_path = full_tensor.get_bytes_path()
        full_cols_path = full_tensor.get_cols_path()

        sids, tids = get_sids_tids(database)
        data, col_inds = extract_tensor_data(tids, features_hash, aggregations_hash)

        ndarray_to_bytes(data, full_bytes_path)
        ndarray_to_bytes(sids, full_ids_path)

        with open(full_cols_path, 'w', encoding='utf-8') as f:
            json.dump(col_inds, f)

        full_tensor.save()
        derived_tensor = DerivedTensorData(name=derived_tensors_name, database=database, full_tensor=full_tensor,
                                           features_hash=features_hash, aggregations_hash=aggregations_hash,
                                           dimreduce='none', creator=admin, annotator=annotator)
        derived_cfg_path = derived_tensor.get_config_path()

        # Always write config last - to make sure it's not missing anything
        embedding = dict(
            tensorName=derived_tensors_name,
            tensorShape=data.shape,
            tensorPath='/' + full_bytes_path,
            metadataPath=reverse('tsne-meta', kwargs={'tensor_name': derived_tensors_name}),
        )
        config = dict(embeddings=[embedding])
        write_config(config, derived_cfg_path)

        derived_tensor.save()

        print('Created full tensor: {}'.format(full_tensors_name))
        print('Created derived tensor: {}'.format(derived_tensors_name))
