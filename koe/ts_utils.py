"""
Utils for tensorflow
"""
import json
import os

import numpy as np


def ndarray_to_bytes(arr, filename):
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.float32

    with open(filename, 'wb') as f:
        arr.tofile(f)


def bytes_to_ndarray(filename):
    with open(filename, 'rb') as f:
        arr = np.fromfile(f, dtype=np.float32)

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


def write_config(config, config_file, tensor_name, tensor_shape, tensor_path, metadata_path):
    json_to_append = dict(
        tensorName=tensor_name,
        tensorShape=tensor_shape,
        tensorPath=tensor_path,
        metadataPath=metadata_path,
    )

    config['embeddings'].append(json_to_append)

    with open(config_file, 'w+') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def write_metadata(metadata, sids, headers, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\t'.join(headers))
        f.write('\n')
        for sid in sids:
            row = metadata[sid]
            f.write('\t'.join(row))
            f.write('\n')
