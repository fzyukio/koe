"""Provides an inteface to store and retrieve numpy arrays in binary file. Store each id as its own file"""

import os

import numpy as np


INDEX_FILE_NCOLS = 3


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


def store(ids, arrs, loc):
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
    assert len(ids) > 0, "lists must be non-empty"
    assert len(ids) == len(arrs), "lists of ids and arrays must have the same length"

    index_file = os.path.join(loc, ".index")
    is_updating = os.path.isfile(index_file)

    update_index_arr = []

    new_file_path_template = os.path.join(loc, "{}.val")
    upd_file_path_template = os.path.join(loc, "{}.val.upd")

    for id, arr in zip(ids, arrs):
        assert np.isscalar(arr) or arr.ndim < 3, "Only scalar, one or two dims arrays are supported"

        arr_len = np.size(arr)
        dim0, dim1 = get_dim(arr)

        # This is somehow necessary - sometimes shape is non-zero even when size is - maybe a numpy bug
        assert arr_len == max(1, dim0) * max(1, dim1)

        if np.isscalar(arr):
            value_arr = np.array([arr], dtype=np.float32).ravel()
        else:
            value_arr = arr.ravel().astype(np.float32)

        new_file_path = new_file_path_template.format(id)
        upd_file_path = upd_file_path_template.format(id)

        if os.path.isfile(new_file_path):
            value_arr.tofile(upd_file_path)
        else:
            value_arr.tofile(new_file_path)

        update_index_arr.append([id, dim0, dim1])

    update_index_arr = np.array(update_index_arr, dtype=np.int32)
    update_index_file = os.path.join(loc, ".index.update")

    if os.path.isfile(update_index_file):
        mode = "ab"
    else:
        mode = "wb"
    with open(update_index_file, mode) as f:
        update_index_arr.tofile(f)

    if not is_updating:
        remake_index(loc)


def remake_index(loc, return_index_arr=False):
    index_file = os.path.join(loc, ".index")
    tmp_index_file = os.path.join(loc, ".index.tmp")
    update_index_file = os.path.join(loc, ".index.update")

    if not os.path.isfile(update_index_file):
        retval = None
        if return_index_arr:
            if os.path.isfile(index_file):
                retval = np.fromfile(index_file, dtype=np.int32).reshape((-1, INDEX_FILE_NCOLS))
            else:
                retval = np.empty((0, 3), dtype=np.int32)
        return retval

    update_index_arr = np.fromfile(update_index_file, dtype=np.int32).reshape((-1, INDEX_FILE_NCOLS))

    if os.path.isfile(index_file):
        index_arr = np.fromfile(index_file, dtype=np.int32).reshape((-1, INDEX_FILE_NCOLS))
    else:
        index_arr = []

    update_id_to_row = {x[0]: x for x in update_index_arr}

    organised_index_arr = []

    for row in index_arr:
        elid = row[0]
        updated_row = update_id_to_row.pop(elid, row)
        organised_index_arr.append(updated_row)

        # if id(row) != id(updated_row):
        #     print('Array {} replaced by {}'.format(row, updated_row))

    for new_row in update_id_to_row.values():
        organised_index_arr.append(new_row)

    organised_index_arr = np.array(organised_index_arr)
    ids = organised_index_arr[:, 0]
    ids_sorted_order = np.argsort(ids)

    organised_index_arr = organised_index_arr[ids_sorted_order, :]

    with open(tmp_index_file, "wb") as f:
        organised_index_arr.tofile(f)

    # Turn on the dirty flag while we are updating files on disk.
    # To update: move all temp value files to actual value files (e.g 1234.val.tmp -> 1234.val)
    dirty_flag_file = os.path.join(loc, ".dirty")
    with open(dirty_flag_file, "w") as f:
        f.write("true")

    update_ids = update_index_arr[:, 0]
    upd_file_template = os.path.join(loc, "{}.val.upd")
    val_file_template = os.path.join(loc, "{}.val")

    for update_id in update_ids:
        upd_file = upd_file_template.format(update_id)
        val_file = val_file_template.format(update_id)

        if os.path.isfile(upd_file):
            os.replace(upd_file, val_file)

    os.replace(tmp_index_file, index_file)
    os.remove(update_index_file)
    os.remove(dirty_flag_file)

    if return_index_arr:
        return organised_index_arr


def retrieve_ids(loc):
    index_arr = remake_index(loc, return_index_arr=True)
    return index_arr[:, 0]


def retrieve(lookup_ids, loc, flat=False):
    index_arr = remake_index(loc, return_index_arr=True)
    all_ids = index_arr[:, 0]

    non_existing_idx = np.where(np.logical_not(np.isin(lookup_ids, all_ids)))
    non_existing_ids = lookup_ids[non_existing_idx]
    if len(non_existing_ids) > 0:
        err_msg = "These IDs don't exist: {}".format(",".join(list(map(str, non_existing_ids))))
        raise ValueError(err_msg)

    lookup_ids_rows = np.searchsorted(all_ids, lookup_ids)
    retval = []

    path_template = os.path.join(loc, "{}.val")

    for ind, id_row in enumerate(lookup_ids_rows):
        id, dim0, dim1 = index_arr[id_row, :]
        path = path_template.format(id)
        data = np.fromfile(path, dtype=np.float32)
        if not flat:
            data = reshape(dim0, dim1, data)
        retval.append(data)

    return retval
