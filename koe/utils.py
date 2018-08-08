"""
General utils for the entire project.
DO NOT import any project-related files here. NO Model, NO form, NO nothing.
model_utils is there you can import those
"""
import base64
import contextlib
import re
import wave
from itertools import product

import numpy as np


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

    m1 = np.full((n, m), True, dtype=np.bool)
    m1 = np.triu(m1, 1)
    arr = mat[m1]
    return arr


@contextlib.contextmanager
def printoptions(*args, **kwargs):
    original = np.get_printoptions()
    np.set_printoptions(*args, **kwargs)
    try:
        yield
    finally:
        np.set_printoptions(**original)


def get_wav_info(audio_file):
    """
    Return fs and length of an audio without readng the entire file
    :param audio_file:
    :return:
    """
    with contextlib.closing(wave.open(audio_file, 'r')) as f:
        nframes = f.getnframes()
        rate = f.getframerate()
    return rate, nframes


def segments(siglen, window, noverlap, incltail=False):
    """
    Calculate how many segments can be extracted from a signal given
    the window size and overlap size
     INPUT:
      - SIGLEN : length of the signal
      - WINDOW : window size (number of samples)
      - NOVERLAP: overlap size (number of samples)
      - INCLTAIL: true to always include the last owner (might be < window)
                    false to exclude it if it's < window
     OUTPUT:
      - NSEGS   : number of segments that can be extracted
      - SEGS    : a two dimensional arrays. Each column is a pair of segments
                   indices
     Example:
      [nsegs, segs] = nsegment(53, 10, 5)
       nsegs = 9
       segs =
         1    10
         6    15
        11    20
        16    25
        21    30
        26    35
        31    40
        36    45
        41    50
      tail:
        51    53
    """
    idx1 = np.arange(0, siglen, window - noverlap)
    idx2 = idx1 + window

    last = np.where(idx2 > siglen)[0][0] + 1
    if idx2[last - 2] == siglen:
        incltail = False
    if incltail:
        nsegs = last
        idx2[nsegs - 1] = siglen
    else:
        nsegs = last - 1

    segs = np.empty((nsegs, 2), dtype=np.uint32)

    segs[:, 0] = idx1[:nsegs]
    segs[:, 1] = idx2[:nsegs]

    return nsegs, segs


def accum(accmap, a, func=None, size=None, fill_value=0, dtype=None):
    """
    An accumulation function similar to Matlab's `accumarray` function.
    Parameters
    ----------
    accmap : ndarray
        This is the "accumulation map".  It maps input (i.e. indices into
        `a`) to their destination in the output array.  The first `a.ndim`
        dimensions of `accmap` must be the same as `a.shape`.  That is,
        `accmap.shape[:a.ndim]` must equal `a.shape`.  For example, if `a`
        has shape (15,4), then `accmap.shape[:2]` must equal (15,4).  In this
        case `accmap[i,j]` gives the index into the output array where
        element (i,j) of `a` is to be accumulated.  If the output is, say,
        a 2D, then `accmap` must have shape (15,4,2).  The value in the
        last dimension give indices into the output array. If the output is
        1D, then the shape of `accmap` can be either (15,4) or (15,4,1)
    a : ndarray
        The input data to be accumulated.
    func : callable or None
        The accumulation function.  The function will be passed a list
        of values from `a` to be accumulated.
        If None, numpy.sum is assumed.
    size : ndarray or None
        The size of the output array.  If None, the size will be determined
        from `accmap`.
    fill_value : scalar
        The default value for elements of the output array.
    dtype : numpy data type, or None
        The data type of the output array.  If None, the data type of
        `a` is used.
    Returns
    -------
    out : ndarray
        The accumulated results.

        The shape of `out` is `size` if `size` is given.  Otherwise the
        shape is determined by the (lexicographically) largest indices of
        the output found in `accmap`.
    Examples
    --------
    >>> from numpy import array, prod
    >>> a = array([[1,2,3],[4,-1,6],[-1,8,9]])
    >>> a
    array([[ 1,  2,  3],
           [ 4, -1,  6],
           [-1,  8,  9]])
    >>> # Sum the diagonals.
    >>> accmap = array([[0,1,2],[2,0,1],[1,2,0]])
    >>> s = accum(accmap, a)
    array([9, 7, 15])
    >>> # A 2D output, from sub-arrays with shapes and positions like this:
    >>> # [ (2,2) (2,1)]
    >>> # [ (1,2) (1,1)]
    >>> accmap = array([
            [[0,0],[0,0],[0,1]],
            [[0,0],[0,0],[0,1]],
            [[1,0],[1,0],[1,1]],
        ])
    >>> # Accumulate using a product.
    >>> accum(accmap, a, func=prod, dtype=float)
    array([[ -8.,  18.],
           [ -8.,   9.]])
    >>> # Same accmap, but create an array of lists of values.
    >>> accum(accmap, a, func=lambda x: x, dtype='O')
    array([[[1, 2, 4, -1], [3, 6]],
           [[-1, 8], [9]]], dtype=object)
    """
    # Check for bad arguments and handle the defaults.
    if accmap.shape[:a.ndim] != a.shape:
        raise ValueError("The initial dimensions of accmap must be the same as a.shape")
    if func is None:
        func = np.sum
    if dtype is None:
        dtype = a.dtype
    if accmap.shape == a.shape:
        accmap = np.expand_dims(accmap, -1)
    adims = tuple(range(a.ndim))
    if size is None:
        size = 1 + np.squeeze(np.apply_over_axes(np.max, accmap, axes=adims))
    size = np.atleast_1d(size)

    # Create an array of python lists of values.
    vals = np.empty(size, dtype='O')
    for s in product(*[range(k) for k in size]):
        vals[s] = []
    for s in product(*[range(k) for k in a.shape]):
        indx = tuple(accmap[s])
        val = a[s]
        vals[indx].append(val)

    # Create the output array.
    out = np.empty(size, dtype=dtype)
    for s in product(*[range(k) for k in size]):
        if not vals[s]:
            out[s] = fill_value
        else:
            out[s] = func(vals[s])

    return out
