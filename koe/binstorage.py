"""
Provides an inteface to store and retrieve numpy arrays in binary file
"""
import numpy as np

INDEX_FILE_NCOLS = 5


def store(ids, arrs, index_filename, value_filename):
    index_arr = []
    value_arr = []

    begin = 0
    sort_order = np.argsort(ids)

    for idx in sort_order:
        id = ids[idx]

        arr = arrs[idx]
        arr_len = np.size(arr)
        end = begin + arr_len
        dim0 = arr.shape[0]
        dim1 = arr.shape[1] if arr.ndim == 2 else 0

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


def retrieve(lookup_ids, index_filename, value_filename):
    with open(index_filename, 'rb') as f:
        index_arr = np.fromfile(f, dtype=np.int32)

    nids = len(index_arr) // INDEX_FILE_NCOLS
    index_arr = index_arr.reshape((nids, INDEX_FILE_NCOLS))

    ids_cols = index_arr[:, 0]
    lookup_ids_rows = np.searchsorted(ids_cols, lookup_ids)

    retval = []

    with open(value_filename, 'rb') as fid:
        for i in lookup_ids_rows:
            _, begin, end, dim0, dim1 = index_arr[i, :]
            shape = (dim0, dim1) if dim1 != 0 else (dim0,)

            fid.seek(begin * 4)
            chunk_size = end - begin
            data = np.fromfile(fid, dtype=np.float32, count=chunk_size).reshape(shape)

            retval.append(data)
    return retval
