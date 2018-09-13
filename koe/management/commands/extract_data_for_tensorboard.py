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
from koe.model_utils import get_or_error
from koe.models import Segment, Feature, Aggregation, Database, FullTensorData, DerivedTensorData
from koe.ts_utils import ndarray_to_bytes, write_config, bytes_to_ndarray, get_rawdata_from_binary
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


def get_sids_tids(database):
    """
    Get ids and tids from all syllables in this database
    :param database:
    :return: sids, tids. sorted by sids
    """
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


def get_binstorage_locations(features, aggregators):
    """
    Deduce the locations of feature binary files and feature-aggregator binary files from their names
    Then return these locations in two dictionaries for lookup convenience
    :param features:
    :param aggregators:
    :return:
    """
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
    return f2bs, fa2bs


def create_full_tensor(database, features, aggregations, recreate):
    features_hash = '-'.join(list(map(str, features.values_list('id', flat=True))))
    aggregations_hash = '-'.join(list(map(str, aggregations.values_list('id', flat=True))))
    aggregators = [aggregator_map[x.name] for x in aggregations]

    full_tensor = FullTensorData.objects.filter(database=database, features_hash=features_hash,
                                                aggregations_hash=aggregations_hash).first()

    if full_tensor and not recreate:
        print('Full tensor {} already exists. If you want to recreate, turn on flag --recreate'
              .format(full_tensor.name))
        return full_tensor, False

    if full_tensor is None:
        full_tensors_name = uuid.uuid4().hex
        full_tensor = FullTensorData(name=full_tensors_name, database=database, features_hash=features_hash,
                                     aggregations_hash=aggregations_hash)
        full_tensor.save()

    full_sids_path = full_tensor.get_sids_path()
    full_bytes_path = full_tensor.get_bytes_path()
    full_cols_path = full_tensor.get_cols_path()

    sids, tids = get_sids_tids(database)
    f2bs, fa2bs = get_binstorage_locations(features, aggregators)
    data, col_inds = extract_rawdata(f2bs, fa2bs, tids, features, aggregators)

    ndarray_to_bytes(data, full_bytes_path)
    ndarray_to_bytes(sids, full_sids_path)

    with open(full_cols_path, 'w', encoding='utf-8') as f:
        json.dump(col_inds, f)

    return full_tensor, True


def create_derived_tensor(full_tensor, annotator, recreate):
    admin = get_or_error(User, dict(username__iexact='superuser'))
    derived_tensor = DerivedTensorData.objects.filter(database=full_tensor.database, full_tensor=full_tensor,
                                                      features_hash=full_tensor.features_hash,
                                                      aggregations_hash=full_tensor.aggregations_hash,
                                                      dimreduce='none', creator=admin, annotator=annotator).first()
    if derived_tensor and not recreate:
        print('Derived tensor {} already exists. If you want to recreate, turn on flag --recreate'
              .format(derived_tensor.name))
        return derived_tensor, False

    if derived_tensor is None:
        derived_tensors_name = uuid.uuid4().hex
        derived_tensor = DerivedTensorData(name=derived_tensors_name, database=full_tensor.database,
                                           full_tensor=full_tensor, features_hash=full_tensor.features_hash,
                                           aggregations_hash=full_tensor.aggregations_hash,
                                           dimreduce='none', creator=admin, annotator=annotator)
        derived_tensor.save()

    derived_cfg_path = derived_tensor.get_config_path()

    full_sids_path = full_tensor.get_sids_path()
    full_bytes_path = full_tensor.get_bytes_path()

    sids = bytes_to_ndarray(full_sids_path, np.int32)
    full_data = get_rawdata_from_binary(full_bytes_path, len(sids))

    # Always write config last - to make sure it's not missing anything
    embedding = dict(
        tensorName=derived_tensor.name,
        tensorShape=full_data.shape,
        tensorPath='/' + full_bytes_path,
        metadataPath=reverse('tsne-meta', kwargs={'tensor_name': derived_tensor.name}),
    )
    config = dict(embeddings=[embedding])
    write_config(config, derived_cfg_path)

    return derived_tensor, True


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--annotator', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who labels this dataset, case insensitive', )
        parser.add_argument('--recreate', dest='recreate', action='store_true', default=False,
                            help='Recreate tensor & all derivatives even if exists. Tensor names are kept the same')

    def handle(self, database_name, annotator_name, recreate, *args, **options):
        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        features = Feature.objects.all().order_by('id')
        aggregations = Aggregation.objects.all().order_by('id')

        full_tensor, ft_created = create_full_tensor(database, features, aggregations, recreate)
        derived_tensor, dt_created = create_derived_tensor(full_tensor, annotator, recreate)

        if ft_created:
            print('Created full tensor: {}'.format(full_tensor.name))
        if dt_created:
            print('Created derived tensor: {}'.format(derived_tensor.name))
