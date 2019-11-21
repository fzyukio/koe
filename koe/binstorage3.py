"""Provides an inteface to store and retrieve numpy arrays in binary file"""
import datetime
from shutil import copyfile

import os
import sys
import numpy as np

INDEX_FILE_NCOLS = 5
BATCH_SIZE = 1000

INDEX_PREFIX = 'index.'
VALUE_PREFIX = 'value.'


PY3 = sys.version_info[0] == 3
if PY3:
    import builtins
else:
    import __builtin__ as builtins

try:
    builtins.profile
except AttributeError:
    builtins.profile = lambda x: x


# @profile
def get_dim(arr):
    if np.isscalar(arr):
        return 0, 0
    elif arr.ndim == 1:
        return arr.shape[0], 0
    else:
        return arr.shape


# @profile
def reshape(dim0, dim1, arr):
    if not dim0:
        return arr[0]
    if not dim1:
        return arr
    return arr.reshape((dim0, dim1))


@profile  # noqa F821
def _store_anew(ids, arrs, index_filename, value_filename):
    assert isinstance(ids, np.ndarray)
    assert len(ids) > 0, 'lists must be non-empty'
    assert len(ids) == len(arrs), 'lists of ids and arrays must have the same length'
    assert ids.ndim == 1
    # sorted_ids, sort_order = np.unique(ids, return_index=True)
    # assert len(sorted_ids) == len(ids), 'IDs must be unique'
    # assert sorted_ids[0] >= 0, 'IDs must be non-negative'

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


@profile  # noqa F821
def _store(new_ids, new_arrs, index_filename, value_filename):
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
        return _store_anew(new_ids, new_arrs, index_filename, value_filename)

    return _update_by_modification(new_ids, new_arrs, index_filename, value_filename)


@profile  # noqa F821
def store(ids, arrs, loc):
    sorted_ids, sorted_order = np.unique(ids, return_index=True)

    assert len(sorted_ids) == len(ids), 'ids must be all unique'
    assert sorted_ids[0] > 0, 'ids must be all positive'

    min_id = sorted_ids[0]
    min_batch_ind = min_id // BATCH_SIZE

    # We need to backtrack one batch in case the smallest ID starts from a number divisible by batch size
    # For example, if BATCH_SIZE is 1000 and min_id = 3000, this ID must be stored in batch 2001-3000.
    # If we don't backtrack, the batch starts from batch 3001-4000 and the min_id will not be saved
    if min_batch_ind * BATCH_SIZE == min_id:
        min_batch_ind -= 1

    ids_batch = []
    arrs_batch = []

    batches = []

    batch_begin = min_batch_ind * BATCH_SIZE + 1
    batch_end = batch_begin + BATCH_SIZE - 1

    for id, ind in zip(sorted_ids, sorted_order):
        arr = arrs[ind]
        if id <= batch_end:
            ids_batch.append(id)
            arrs_batch.append(arr)
        else:
            batches.append((batch_begin, batch_end, ids_batch, arrs_batch))
            while id > batch_end:
                batch_end += BATCH_SIZE
            batch_begin = batch_end - BATCH_SIZE + 1

            ids_batch = [id]
            arrs_batch = [arr]

    batches.append((batch_begin, batch_end, ids_batch, arrs_batch))

    for batch_begin, batch_end, ids_batch, arrs_batch in batches:
        index_filename = os.path.join(loc, '{}{}-{}'.format(INDEX_PREFIX, batch_begin, batch_end))
        value_filename = os.path.join(loc, '{}{}-{}'.format(VALUE_PREFIX, batch_begin, batch_end))

        ids_batch = np.array(ids_batch, dtype=np.int32)
        _store(ids_batch, arrs_batch, index_filename, value_filename)


def _update_by_modification(new_ids, new_arrs, index_filename, value_filename):
    with open(index_filename, 'rb') as f:
        index_arr = np.fromfile(f, dtype=np.int32)
    index_arr = index_arr.reshape((-1, INDEX_FILE_NCOLS))
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
        new_dim0, new_dim1 = get_dim(new_arr)
        if isinstance(new_arr, np.ndarray):
            new_arr = new_arr.astype(np.float32)
        else:
            new_arr = np.array(new_arr, dtype=np.float32)
        new_len = np.size(new_arr)

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


def retrieve_ids(loc, limit=None):
    batches = {}
    if limit is None:
        index_files = [x for x in os.listdir(loc) if x.startswith(INDEX_PREFIX)]
        if len(index_files) == 0:
            return np.empty((0, INDEX_FILE_NCOLS))
        for index_file in index_files:
            batch_begin, batch_end = list(map(int, index_file[len(INDEX_PREFIX):].split('-')))
            batches[batch_begin] = (batch_begin, batch_end, index_file)

        batch_begins = sorted(list(batches.keys()))

    else:
        min_id, max_id = limit
        min_batch_ind = min_id // BATCH_SIZE
        max_batch_ind = max_id // BATCH_SIZE + 1
        # We need to backtrack one batch in case the smallest ID starts from a number divisible by batch size
        # For example, if BATCH_SIZE is 1000 and min_id = 3000, this ID must be stored in batch 2001-3000.
        # If we don't backtrack, the batch starts from batch 3001-4000 and the min_id will not be saved

        if min_batch_ind * BATCH_SIZE == min_id:
            min_batch_ind -= 1

        batch_begins = []

        for batch_ind in range(min_batch_ind, max_batch_ind + 1):
            batch_begin = batch_ind * BATCH_SIZE + 1
            batch_end = batch_begin + BATCH_SIZE - 1
            index_file = '{}{}-{}'.format(INDEX_PREFIX, batch_begin, batch_end)
            index_filename = os.path.join(loc, index_file)
            if os.path.isfile(index_filename):
                batch_begins.append(batch_begin)
                batches[batch_begin] = (batch_begin, batch_end, index_file)

    ids_cols = []

    for batch_begin in batch_begins:
        batch_begin, batch_end, index_file = batches[batch_begin]

        index_file_full_path = os.path.join(loc, index_file)
        index_arr = np.fromfile(index_file_full_path, dtype=np.int32).reshape((-1, INDEX_FILE_NCOLS))
        ids_cols.append(index_arr[:, 0])

    if len(ids_cols):
        return np.concatenate(ids_cols)
    else:
        return np.array([], dtype=np.int32)


# @profile
def _retrieve(lookup_ids, index_filename, value_filename, flat=False):
    with open(index_filename, 'rb') as f:
        index_arr = np.fromfile(f, dtype=np.int32)

    index_arr = index_arr.reshape((-1, INDEX_FILE_NCOLS))

    ids_cols = index_arr[:, 0]
    sorted_ids, sort_order = np.unique(ids_cols, return_index=True)

    non_existing_idx = np.where(np.logical_not(np.isin(lookup_ids, sorted_ids)))
    non_existing_ids = lookup_ids[non_existing_idx]

    if len(non_existing_ids) > 0:
        err_msg = 'Unable to retrieve IDs {} from {}'.format(','.join(list(map(str, non_existing_ids))), index_filename)
        raise ValueError(err_msg)

    lookup_ids_rows = np.searchsorted(sorted_ids, lookup_ids)

    # We sort the lookup row indices by their start time to minimise number of seek
    sort_order_by_start = np.argsort(index_arr[lookup_ids_rows, 1])
    retval = [None] * len(lookup_ids)

    value_arr = np.fromfile(value_filename, dtype=np.float32)

    for sorted_i in sort_order_by_start:
        lookup_row_ind = sort_order[lookup_ids_rows[sorted_i]]

        _, begin, end, dim0, dim1 = index_arr[lookup_row_ind, :]

        data = value_arr[begin:end]

        if not flat:
            data = reshape(dim0, dim1, data)
        retval[sorted_i] = data
    return retval


# @profile
def retrieve(lookup_ids, loc, flat=False):
    sorted_order = np.argsort(lookup_ids)
    min_id = lookup_ids[sorted_order[0]]

    min_batch_ind = min_id // BATCH_SIZE
    # We need to backtrack one batch in case the smallest ID starts from a number divisible by batch size
    # For example, if BATCH_SIZE is 1000 and min_id = 3000, this ID must be stored in batch 2001-3000.
    # If we don't backtrack, the batch starts from batch 3001-4000 and the min_id will not be saved
    if min_batch_ind * BATCH_SIZE == min_id:
        min_batch_ind -= 1

    ids_batch = []
    inds_batch = []
    batches = []

    batch_begin = min_batch_ind * BATCH_SIZE + 1
    batch_end = batch_begin + BATCH_SIZE - 1

    for ind in sorted_order:
        id = lookup_ids[ind]
        if id <= batch_end:
            ids_batch.append(id)
            inds_batch.append(ind)
        else:
            batches.append((batch_begin, batch_end, ids_batch, inds_batch))
            while id > batch_end:
                batch_end += BATCH_SIZE
            batch_begin = batch_end - BATCH_SIZE + 1

            ids_batch = [id]
            inds_batch = [ind]

    batches.append((batch_begin, batch_end, ids_batch, inds_batch))

    arrs = [None] * len(lookup_ids)

    for batch_begin, batch_end, ids_batch, inds_batch in batches:
        index_filename = os.path.join(loc, '{}{}-{}'.format(INDEX_PREFIX, batch_begin, batch_end))
        value_filename = os.path.join(loc, '{}{}-{}'.format(VALUE_PREFIX, batch_begin, batch_end))

        ids_batch = np.array(ids_batch, dtype=np.int32)
        arr = _retrieve(ids_batch, index_filename, value_filename, flat)

        for ind, value in zip(inds_batch, arr):
            arrs[ind] = value

    return arrs


def retrieve_raw(loc):
    index_files = [x for x in os.listdir(loc) if x.startswith(INDEX_PREFIX)]
    if len(index_files) == 0:
        return np.empty((0, INDEX_FILE_NCOLS))
    batches = {}
    for index_file in index_files:
        batch_begin, batch_end = list(map(int, index_file[len(INDEX_PREFIX):].split('-')))
        batches[batch_begin] = (batch_begin, batch_end)

    ids = []
    arrs = []

    batch_begins = sorted(list(batches.keys()))
    for batch_begin in batch_begins:
        batch_begin, batch_end = batches[batch_begin]
        index_filename = os.path.join(loc, '{}{}-{}'.format(INDEX_PREFIX, batch_begin, batch_end))
        value_filename = os.path.join(loc, '{}{}-{}'.format(VALUE_PREFIX, batch_begin, batch_end))

        index_arr = np.fromfile(index_filename, dtype=np.int32).reshape((-1, INDEX_FILE_NCOLS))

        value_arr = np.fromfile(value_filename, dtype=np.float32)
        for id, begin, end, dim0, dim1 in index_arr:
            data = value_arr[begin:end]
            data = reshape(dim0, dim1, data)
            arrs.append(data)
            ids.append(id)

    ids = np.array(ids, dtype=np.int32)
    return ids, arrs
