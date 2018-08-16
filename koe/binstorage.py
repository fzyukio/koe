"""
Provides an inteface to store and retrieve numpy arrays in binary file
"""
import datetime
import os

import numpy as np

INDEX_FILE_NCOLS = 5


def store_or_update(ids, arrs, index_filename, value_filename):
    assert isinstance(ids, np.ndarray)
    assert len(ids) > 0, 'lists must be non-empty'
    assert len(ids) == len(arrs), 'lists of ids and arrays must have the same length'
    assert ids.ndim == 1
    sorted_ids, sort_order = np.unique(ids, return_index=True)
    assert len(sorted_ids) == len(ids), 'IDs must be unique'
    assert sorted_ids[0] >= 0, 'IDs must be non-negative'

    index_arr = []
    value_arr = []

    begin = 0

    for idx in sort_order:
        id = ids[idx]

        arr = arrs[idx]
        assert arr.ndim < 3, 'Only scalar, one or two dims arrays are supported'

        arr_len = np.size(arr)
        end = begin + arr_len

        dim0 = arr.shape[0] if arr.ndim > 0 else 0
        dim1 = arr.shape[1] if arr.ndim == 2 else 0

        # This is somehow necessary - sometimes shape is non-zero even when size is - maybe a numpy bug
        assert arr_len == max(1, dim0) * max(1, dim1)

        index_arr.append([id, begin, end, dim0, dim1])
        value_arr.append(arr.ravel())

        begin = end

    index_arr = np.array(index_arr, dtype=np.int32)
    value_arr = np.concatenate(value_arr).astype(np.float32)

    with open(index_filename, 'wb') as f:
        index_arr.tofile(f)

    with open(value_filename, 'wb') as f:
        value_arr.tofile(f)

    return index_filename, value_filename


def store(new_ids, new_arrs, index_filename, value_filename):
    """
    If files don't exit, create new. Otherwise update existing
    Append or update ids and array values in given files.
    For now, just reload the file, add new ids, then rewrite it again
    :param new_ids: np.ndarray of IDs to append
    :param new_arrs: list of arrays to append
    :param index_filename:
    :param value_filename:
    :return:
    """
    index_ifle_exists = os.path.isfile(index_filename)
    value_file_exists = os.path.isfile(value_filename)
    if index_ifle_exists and value_file_exists:
        is_creating = False
    elif not index_ifle_exists and not value_file_exists:
        is_creating = True
    else:
        raise RuntimeError('Index and value files must either both exist or both not exist')

    if is_creating:
        index_arr = np.array([], dtype=np.int32)
        value_bin = np.array([], dtype=np.float32)
    else:
        with open(index_filename, 'rb') as f:
            index_arr = np.fromfile(f, dtype=np.int32)
        nids = len(index_arr) // INDEX_FILE_NCOLS
        index_arr = index_arr.reshape((nids, INDEX_FILE_NCOLS))

        with open(value_filename, 'rb') as f:
            value_bin = np.fromfile(f, dtype=np.float32)

    new_id2arr = {x: y for x, y in zip(new_ids, new_arrs)}

    for id, start, end, dim0, dim1 in index_arr:
        if id not in new_id2arr:
            arr = value_bin[start: end]
            if dim0 > 0:
                shape = (dim0, dim1) if dim1 != 0 else (dim0,)
                arr = arr.reshape(shape)
            else:
                assert np.size(arr) == 1
                arr = arr[0]
            new_id2arr[id] = arr

    ids = np.array(list(new_id2arr.keys()), dtype=np.int32)
    arrs = list(new_id2arr.values())

    if not is_creating:
        # Make a backup before overwriting the file, then delete the backup if anything happens
        time_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        bak_index_file = '{}.bak_{}'.format(index_filename, time_str)
        bak_value_file = '{}.bak_{}'.format(value_filename, time_str)

        os.replace(index_filename, bak_index_file)
        os.replace(value_filename, bak_value_file)

    try:
        store_or_update(ids, arrs, index_filename, value_filename)
    except Exception as e:
        if not is_creating:
            os.replace(bak_index_file, index_filename)
            os.replace(bak_value_file, value_filename)
        raise e

    if not is_creating:
        os.remove(bak_index_file)
        os.remove(bak_value_file)


def retrieve(lookup_ids, index_filename, value_filename):
    with open(index_filename, 'rb') as f:
        index_arr = np.fromfile(f, dtype=np.int32)

    nids = len(index_arr) // INDEX_FILE_NCOLS
    index_arr = index_arr.reshape((nids, INDEX_FILE_NCOLS))

    ids_cols = index_arr[:, 0]
    lookup_ids_rows = np.searchsorted(ids_cols, lookup_ids)

    non_existing_idx = np.where(lookup_ids_rows >= len(ids_cols))[0]
    if len(non_existing_idx) > 0:
        non_existing_ids = lookup_ids[non_existing_idx]
        err_msg = 'These IDs don\'t exist: {}'.format(','.join(list(map(str, non_existing_ids))))
        raise ValueError(err_msg)

    retval = []

    with open(value_filename, 'rb') as fid:
        for i in lookup_ids_rows:
            _, begin, end, dim0, dim1 = index_arr[i, :]

            fid.seek(begin * 4)
            chunk_size = end - begin
            data = np.fromfile(fid, dtype=np.float32, count=chunk_size)

            if dim0 > 0:
                shape = (dim0, dim1) if dim1 != 0 else (dim0,)
                data = data.reshape(shape)
            else:
                assert np.size(data) == 1
                data = data[0]

            retval.append(data)
    return retval
