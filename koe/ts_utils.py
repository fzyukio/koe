"""
Utils for tensorflow
"""
import json
import os
import uuid

import io
import numpy as np
from django.conf import settings
from django.urls import reverse

from koe.models import Segment, DerivedTensorData
from root.models import ExtraAttrValue
from root.utils import ensure_parent_folder_exists

from sklearn.decomposition import PCA as pca, FastICA as ica

reduce_funcs = {
    'ica': ica,
    'pca': pca,
    'none': None
}


def ndarray_to_bytes(arr, filename):
    assert isinstance(arr, np.ndarray)

    ensure_parent_folder_exists(filename)
    with open(filename, 'wb') as f:
        arr.tofile(f)


def bytes_to_ndarray(filename, dtype=np.float32):
    with open(filename, 'rb') as f:
        arr = np.fromfile(f, dtype=dtype)

    return arr


def load_config(config_file):
    if os.path.isfile(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = dict(embeddings=[])

    return config


def get_safe_tensors_name(config, tensors_name):
    embeddings = config['embeddings']

    existing_tensors = [x['tensorName'] for x in embeddings]
    new_tensors_name = tensors_name
    appendix = 0
    while new_tensors_name in existing_tensors:
        appendix += 1
        new_tensors_name = '{}_{}'.format(tensors_name, appendix)

    return new_tensors_name


def write_config(config, config_file):
    ensure_parent_folder_exists(config_file)

    with open(config_file, 'w+') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def write_metadata(metadata, sids, headers, filename=None):
    if filename:
        ensure_parent_folder_exists(filename)
        output_stream = open(filename, 'w', encoding='utf-8')
    else:
        output_stream = io.StringIO()

    output_stream.write('\t'.join(headers))
    output_stream.write('\n')
    for sid in sids:
        row = metadata[sid]
        output_stream.write('\n')
        output_stream.write('\t'.join(row))

    if not filename:
        content = output_stream.getvalue()
        output_stream.close()
        return content


def get_tensor_file_paths(config_name, tensors_name):
    binary_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.bytes'.format(tensors_name))[1:]
    metadata_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.tsv'.format(tensors_name))[1:]
    config_file = os.path.join(settings.MEDIA_URL, 'oss_data', '{}.json'.format(config_name))[1:]
    columns_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.json'.format(tensors_name))[1:]

    return config_file, binary_path, metadata_path, columns_path


def get_sids_from_metadata(filename):
    sids = []
    with open(filename, 'r', encoding='utf-8') as f:
        f.readline()
        line = f.readline()
        while line:
            id = int(line[:line.find('\t')])
            sids.append(id)
            line = f.readline()
    return sids


def get_rawdata_from_binary(filename, nrows):
    arr = bytes_to_ndarray(filename)
    size = np.size(arr)
    return arr.reshape((nrows, size // nrows))


def cherrypick_tensor_data_by_feature_aggreation(full_data, col_inds, features, aggregations):
    rawdata = []

    for feature in features:
        if feature.is_fixed_length:
            start, end = col_inds[feature.name]
            rawdata_stacked = full_data[:, start:end]
            rawdata.append(rawdata_stacked)

        else:
            for aggregation in aggregations:
                start, end = col_inds['{}_{}'.format(feature.name, aggregation.name)]
                rawdata_stacked = full_data[:, start:end]
                rawdata.append(rawdata_stacked)

    rawdata = np.concatenate(rawdata, axis=1)
    return rawdata


def cherrypick_tensor_data_by_sids(full_data, full_sids, sids):
    sorted_ids, sort_order = np.unique(full_sids, return_index=True)

    non_existing_idx = np.where(np.logical_not(np.isin(sids, sorted_ids)))
    non_existing_ids = sids[non_existing_idx]

    if len(non_existing_ids) > 0:
        err_msg = 'These IDs don\'t exist: {}'.format(','.join(list(map(str, non_existing_ids))))
        raise ValueError(err_msg)

    lookup_ids_rows = np.searchsorted(sorted_ids, sids)
    return full_data[lookup_ids_rows, :]


def make_subtensor(user, full_tensor, annotator, features, aggregations, dimreduce, ndims):
    reduce_func = reduce_funcs[dimreduce]
    if not reduce_func:
        ndims = None

    full_sids_path = full_tensor.get_sids_path()
    full_bytes_path = full_tensor.get_bytes_path()
    full_cols_path = full_tensor.get_cols_path()

    sids = bytes_to_ndarray(full_sids_path, np.int32)

    full_data = get_rawdata_from_binary(full_bytes_path, len(sids))
    with open(full_cols_path, 'r', encoding='utf-8') as f:
        col_inds = json.load(f)

    new_data = cherrypick_tensor_data_by_feature_aggreation(full_data, col_inds, features, aggregations)
    if reduce_func:
        dim_reduce_func = reduce_func(n_components=ndims)
        new_data = dim_reduce_func.fit_transform(new_data)

    new_tensor_name = uuid.uuid4().hex
    features_hash = '-'.join(list(map(str, features.values_list('id', flat=True))))
    aggregations_hash = '-'.join(list(map(str, aggregations.values_list('id', flat=True))))

    new_tensor = DerivedTensorData(name=new_tensor_name, annotator=annotator, full_tensor=full_tensor,
                                   database=full_tensor.database, features_hash=features_hash,
                                   aggregations_hash=aggregations_hash, creator=user,
                                   dimreduce=dimreduce, ndims=ndims)

    new_bytes_path = new_tensor.get_bytes_path()
    new_config_path = new_tensor.get_config_path()

    ndarray_to_bytes(new_data, new_bytes_path)

    embedding = dict(
        tensorName=new_tensor_name,
        tensorShape=new_data.shape,
        tensorPath='/' + new_bytes_path,
        metadataPath=reverse('tsne-meta', kwargs={'tensor_name': new_tensor_name}),
    )

    config = dict(embeddings=[embedding])

    write_config(config, new_config_path)
    new_tensor.save()

    return new_tensor


def extract_tensor_metadata(sids, annotator):
    metadata = {sid: [str(sid)] for sid in sids}

    label_levels = ['label', 'label_family']
    headers = ['id'] + label_levels + ['gender']

    for i in range(len(label_levels)):
        label_level = label_levels[i]
        segment_to_label =\
            {
                x: y.lower() for x, y in ExtraAttrValue.objects
                .filter(attr__name=label_level, attr__klass=Segment.__name__, owner_id__in=sids,
                        user=annotator)
                .order_by('owner_id')
                .values_list('owner_id', 'value')
            }

        for sid in sids:
            metadata[sid].append(segment_to_label.get(sid, ''))

    sid_to_gender =\
        {
            x: y.lower() for x, y in Segment.objects.filter(id__in=sids).order_by('id')
            .values_list('id', 'audio_file__individual__gender')
        }

    for sid in sids:
        metadata[sid].append(sid_to_gender.get(sid, ''))

    return metadata, headers
