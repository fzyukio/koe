import base64
import re
import io
import binascii

import numpy as np
import joblib


def gzip_ndarray(arr):
    out = io.BytesIO()
    joblib.dump(arr, out, compress=('zlib', 1))
    value = out.getvalue()
    out.close()
    return value


def gunzip_byte(barr):
    in_ = io.BytesIO()
    in_.write(barr)
    in_.seek(0)
    return joblib.load(in_)


def array_to_compressed_base64(array):
    # Compress array to bytes:
    arr_z = gzip_ndarray(array)
    b64_arr_z = binascii.b2a_base64(arr_z)

    return b64_arr_z


def compressed_base64_to_array(b64_arr_z):
    arr_z = binascii.a2b_base64(b64_arr_z)
    return gunzip_byte(arr_z)


def array_to_base64(array):
    return '{}{}::{}'.format(array.dtype, np.shape(array), base64.b64encode(array).decode("ascii"))


def base64_to_array(string):
    a = string.index('(')
    b = string.index(')')

    dtype = string[:a]
    shape = list(map(int, re.sub(r',?\)', '', string[a + 1:b + 1]).split(', ')))
    encoded = string[b + 3:]

    array = np.frombuffer(base64.decodebytes(encoded.encode()), dtype=np.dtype(dtype)).reshape(shape)
    return array


def triu2mat(triu):
    if np.size(np.shape(triu)) > 1:
        raise Exception('dist must be array')

    n = int(np.math.ceil(np.math.sqrt(np.size(triu) * 2)))
    if np.size(triu) != n * (n - 1) / 2:
        raise Exception('dist must have n*(n-1)/2 elements')

    retval = np.zeros((n, n), dtype=triu.dtype)
    retval[np.triu_indices(n, 1)] = triu

    return retval + retval.T


def mat2triu(mat):
    if np.size(np.shape(mat)) == 1:
        raise Exception('Argument must be a square matrix')

    n, m = np.shape(mat)
    if n != m:
        raise Exception('Argument must be a square matrix')

    m1 = np.full((n,m), True, dtype=np.bool)
    m1 = np.triu(m1, 1)
    arr = mat[m1]
    return arr

