"""
Run tsne with different numbers of dimensions, svm and export result
"""
import json
import uuid

import numpy as np
from django.core.management.base import BaseCommand
from django.urls import reverse
from scipy.stats import zscore

from koe.aggregator import aggregator_map
from koe.feature_utils import extract_rawdata
from koe.model_utils import get_or_error
from koe.models import Feature, Aggregation, Database, FullTensorData, DerivedTensorData

from koe.storage_utils import get_sids_tids
from koe.ts_utils import ndarray_to_bytes, write_config, bytes_to_ndarray, get_rawdata_from_binary, reduce_funcs
from root.models import User


def create_full_tensor(database, recreate):
    features = Feature.objects.all().order_by('id')
    aggregations = Aggregation.objects.all().order_by('id')
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

    full_sids_path = full_tensor.get_sids_path()
    full_bytes_path = full_tensor.get_bytes_path()
    full_cols_path = full_tensor.get_cols_path()

    sids, tids = get_sids_tids(database)
    data, col_inds = extract_rawdata(tids, features, aggregators)

    ndarray_to_bytes(data, full_bytes_path)
    ndarray_to_bytes(sids, full_sids_path)

    with open(full_cols_path, 'w', encoding='utf-8') as f:
        json.dump(col_inds, f)

    full_tensor.save()
    return full_tensor, True


def create_derived_tensor(full_tensor, annotator, dim_reduce, ndims, recreate):
    admin = get_or_error(User, dict(username__iexact='superuser'))
    full_sids_path = full_tensor.get_sids_path()
    full_bytes_path = full_tensor.get_bytes_path()

    sids = bytes_to_ndarray(full_sids_path, np.int32)
    full_data = get_rawdata_from_binary(full_bytes_path, len(sids))

    if dim_reduce != 'none':
        dim_reduce_fun = reduce_funcs[dim_reduce]
        n_feature_cols = full_data.shape[1]
        n_components = min(n_feature_cols // 2, ndims)
    else:
        dim_reduce_fun = None
        n_components = None

    derived_tensor = DerivedTensorData.objects.filter(database=full_tensor.database, full_tensor=full_tensor,
                                                      features_hash=full_tensor.features_hash,
                                                      aggregations_hash=full_tensor.aggregations_hash,
                                                      ndims=n_components, dimreduce=dim_reduce, creator=admin,
                                                      annotator=annotator).first()
    if derived_tensor and not recreate:
        print('Derived tensor {} already exists. If you want to recreate, turn on flag --recreate'
              .format(derived_tensor.name))
        return derived_tensor, False

    if derived_tensor is None:
        derived_tensors_name = uuid.uuid4().hex
        derived_tensor = DerivedTensorData(name=derived_tensors_name, database=full_tensor.database,
                                           full_tensor=full_tensor, features_hash=full_tensor.features_hash,
                                           aggregations_hash=full_tensor.aggregations_hash, dimreduce=dim_reduce,
                                           ndims=n_components, creator=admin, annotator=annotator)

    derived_cfg_path = derived_tensor.get_config_path()

    if dim_reduce_fun:

        # TSNE needs normalisation first
        if dim_reduce.startswith('tsne'):
            full_data = zscore(full_data)
            full_data[np.where(np.isnan(full_data))] = 0
            full_data[np.where(np.isinf(full_data))] = 0

        dim_reduced_data = dim_reduce_fun(full_data, n_components)
        derived_bytes_path = derived_tensor.get_bytes_path()
        ndarray_to_bytes(dim_reduced_data, derived_bytes_path)
        tensor_shape = dim_reduced_data.shape
        tensor_path = '/' + derived_bytes_path,
    else:
        tensor_shape = full_data.shape
        tensor_path = '/' + full_bytes_path,

    # Always write config last - to make sure it's not missing anything
    embedding = dict(
        tensorName=derived_tensor.name,
        tensorShape=tensor_shape,
        tensorPath=tensor_path,
        metadataPath=reverse('tsne-meta', kwargs={'tensor_name': derived_tensor.name}),
    )
    config = dict(embeddings=[embedding])
    write_config(config, derived_cfg_path)

    derived_tensor.save()
    return derived_tensor, True


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--annotator', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who labels this dataset, case insensitive', )
        parser.add_argument('--dim-reduce', action='store', dest='dim_reduce', default='none', type=str,
                            help='Currrently support pca, ica, tsne, mds', )
        parser.add_argument('--ndims', action='store', dest='ndims', default=None, type=int,
                            help='Number of dimensions to reduce to. Required if --dim-reduce is not none', )
        parser.add_argument('--recreate', dest='recreate', action='store', default=None, type=str,
                            help='Choose from "all", "full", "derived". Tensor names are kept the same')

    def handle(self, database_name, annotator_name, dim_reduce, ndims, recreate, *args, **options):
        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        assert dim_reduce in reduce_funcs.keys(), 'Unknown function: {}'.format(dim_reduce)
        if dim_reduce != 'none' and ndims is None:
            raise Exception('ndims is required when --dim-reduce is not none')

        recreate_full = recreate in ['all', 'full']
        recreate_derived = recreate in ['all', 'derived']
        full_tensor, ft_created = create_full_tensor(database, recreate_full)
        derived_tensor, dt_created = create_derived_tensor(full_tensor, annotator, dim_reduce, ndims, recreate_derived)

        if ft_created:
            print('Created full tensor: {}'.format(full_tensor.name))
        if dt_created:
            print('Created derived tensor: {}'.format(derived_tensor.name))
