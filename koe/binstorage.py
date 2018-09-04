"""
Provides an inteface to store and retrieve numpy arrays in binary file
"""
import datetime
import os

import numpy as np
from shutil import copyfile

INDEX_FILE_NCOLS = 5


def get_dim(arr):
    if np.isscalar(arr):
        return 0, 0
    elif arr.ndim == 1:
        return arr.shape[0], 0
    else:
        return arr.shape


def reshape(dim0, dim1, arr):
    if dim0 == 0:
        return arr[0]
    if dim1 == 0:
        return arr
    return arr.reshape((dim0, dim1))


def store_anew(ids, arrs, index_filename, value_filename):
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

    for id, arr in zip(ids, arrs):
        assert np.isscalar(arr) or arr.ndim < 3, 'Only scalar, one or two dims arrays are supported'

        arr_len = np.size(arr)
        end = begin + arr_len
        dim0, dim1 = get_dim(arr)

        # This is somehow necessary - sometimes shape is non-zero even when size is - maybe a numpy bug
        assert arr_len == max(1, dim0) * max(1, dim1)

        index_arr.append([id, begin, end, dim0, dim1])
        if np.isscalar(arr):
            value_arr.append(np.array([arr], dtype=np.float32).ravel())
        else:
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
    index_file_exists = os.path.isfile(index_filename)
    value_file_exists = os.path.isfile(value_filename)
    if index_file_exists and value_file_exists:
        is_creating = False
    elif not index_file_exists and not value_file_exists:
        is_creating = True
    else:
        raise RuntimeError('Index and value files must either both exist or both not exist')

    if is_creating:
        return store_anew(new_ids, new_arrs, index_filename, value_filename)

    index_filesize = os.path.getsize(index_filename)
    n_exiting = index_filesize // 4 // INDEX_FILE_NCOLS

    if len(new_ids) >= n_exiting // 3:
        return update_by_recreating(new_ids, new_arrs, index_filename, value_filename)

    return update_by_modification(new_ids, new_arrs, index_filename, value_filename)


def update_by_modification(new_ids, new_arrs, index_filename, value_filename):
    with open(index_filename, 'rb') as f:
        index_arr = np.fromfile(f, dtype=np.int32)
    nids = len(index_arr) // INDEX_FILE_NCOLS
    index_arr = index_arr.reshape((nids, INDEX_FILE_NCOLS))
    index_arr = index_arr.tolist()

    with open(value_filename, 'rb') as f:
        value_bin = np.fromfile(f, dtype=np.float32)

    id2info = {}
    id2row_idx = {}
    for idx, (id, start, end, dim0, dim1) in enumerate(index_arr):
        id2info[id] = (start, end, dim0, dim1)
        id2row_idx[id] = idx

    to_update = {}
    to_append = {}

    new_start = len(value_bin)

    for new_id, new_arr in zip(new_ids, new_arrs):
        new_arr = new_arr.astype(np.float32)
        new_len = np.size(new_arr)
        new_dim0, new_dim1 = get_dim(new_arr)

        if new_id in id2info:
            start, end, dim0, dim1 = id2info[new_id]
            old_len = end - start

            # If the new array is smaller or same size: replace the data, not append
            # In case it is smaller, there will be left-over, untrimmed freespace, which is fine
            if new_len <= old_len:
                end = start + new_len
                to_update[new_id] = (start, end, new_dim0, new_dim1, new_arr)

            # Otherwise we must append the updated data, leaving the old data unreferenced and untrimmed
            else:
                start = new_start
                end = start + new_len
                new_start += new_len
                to_append[new_id] = (start, end, new_dim0, new_dim1, new_arr)

            idx = id2row_idx[new_id]
            index_arr[idx] = [new_id, start, end, new_dim0, new_dim1]

        else:
            start = new_start
            end = start + new_len
            new_start += new_len
            to_append[new_id] = (start, end, new_dim0, new_dim1, new_arr)
            index_arr.append([new_id, start, end, new_dim0, new_dim1])

    index_arr = np.array(index_arr, dtype=np.int32)

    # Make a backup before overwriting the file, then delete the backup if anything happens
    time_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    bak_index_file = '{}.bak_{}'.format(index_filename, time_str)
    bak_value_file = '{}.bak_{}'.format(value_filename, time_str)

    copyfile(index_filename, bak_index_file)
    copyfile(value_filename, bak_value_file)

    try:
        with open(index_filename, 'wb') as f:
            index_arr.tofile(f)

        with open(value_filename, 'r+b') as fid:
            for id, (start, end, dim0, dim1, new_arr) in to_update.items():

                fid.seek(start * 4)
                new_arr.tofile(fid)

        with open(value_filename, 'ab') as fid:
            for id, (start, end, dim0, dim1, new_arr) in to_append.items():
                new_arr.tofile(fid)

    except Exception as e:
        os.replace(bak_index_file, index_filename)
        os.replace(bak_value_file, value_filename)
        raise e

    os.remove(bak_index_file)
    os.remove(bak_value_file)


def update_by_recreating(new_ids, new_arrs, index_filename, value_filename):
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

    # Make a backup before overwriting the file, then delete the backup if anything happens
    time_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    bak_index_file = '{}.bak_{}'.format(index_filename, time_str)
    bak_value_file = '{}.bak_{}'.format(value_filename, time_str)

    os.replace(index_filename, bak_index_file)
    os.replace(value_filename, bak_value_file)

    try:
        store_anew(ids, arrs, index_filename, value_filename)
    except Exception as e:
        os.replace(bak_index_file, index_filename)
        os.replace(bak_value_file, value_filename)
        raise e

    os.remove(bak_index_file)
    os.remove(bak_value_file)


def retrieve(lookup_ids, index_filename, value_filename, flat=False):
    with open(index_filename, 'rb') as f:
        index_arr = np.fromfile(f, dtype=np.int32)

    nids = len(index_arr) // INDEX_FILE_NCOLS
    index_arr = index_arr.reshape((nids, INDEX_FILE_NCOLS))

    ids_cols = index_arr[:, 0]
    sorted_ids, sort_order = np.unique(ids_cols, return_index=True)

    non_existing_idx = np.where(np.logical_not(np.isin(lookup_ids, sorted_ids)))
    non_existing_ids = lookup_ids[non_existing_idx]

    if len(non_existing_ids) > 0:
        err_msg = 'These IDs don\'t exist: {}'.format(','.join(list(map(str, non_existing_ids))))
        raise ValueError(err_msg)

    lookup_ids_rows = np.searchsorted(sorted_ids, lookup_ids)

    # We sort the lookup row indices by their start time to minimise number of seek
    sort_order_by_start = np.argsort(index_arr[lookup_ids_rows, 1])
    retval = [None] * len(lookup_ids)

    with open(value_filename, 'rb') as fid:
        for sorted_i in sort_order_by_start:
            lookup_row_ind = sort_order[lookup_ids_rows[sorted_i]]

            _, begin, end, dim0, dim1 = index_arr[lookup_row_ind, :]

            fid.seek(begin * 4)
            chunk_size = end - begin
            data = np.fromfile(fid, dtype=np.float32, count=chunk_size)
            if not flat:
                data = reshape(dim0, dim1, data)
            retval[sorted_i] = data
    return retval
