"""
General utils for the entire project.
DO NOT import any project-related files here. NO Model, NO form, NO nothing.
model_utils is there you can import those
"""
import os
import base64
import contextlib
import re
import wave
from itertools import product

import numpy as np

from root.utils import data_path


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


def split_segments(siglen, window, noverlap, incltail=False):
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

    return nsegs, segs.tolist()


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


def get_kfold_indices(labels, k):
    """
    Create a training set indices and test set indices such that the k-ratio is preserved for all classes
    This function is better suited for unbalanced data, e.g. some classes only have very few instances, such that
     the normal way (randomised then split k-ways) might end up having some instances having no instances in the
     training or test set
    :param labels: 1-D array (int) contains enumerated labels
    :param k:
    :return: k-item array. Each element is a dict(test=test_indices, train=train_indices). The indices are randomised
    """
    assert isinstance(labels, np.ndarray) and len(labels.shape) == 1, 'labels must be a 1-D numpy array'

    label_sorted_indices = np.argsort(labels)
    sorted_labels = labels[label_sorted_indices]

    uniques, counts = np.unique(sorted_labels, return_counts=True)

    if np.any(counts < k):
        raise ValueError('Value of k={} is too big - there are classes that have less than {} instances'.format(k, k))

    nclasses = len(uniques)

    fold_indices = np.ndarray((len(labels),), dtype=np.int32)

    grant_added = 0

    for i in range(nclasses):
        ninstances = counts[i]
        nremainings = ninstances
        label = uniques[i]
        instance_indices = np.where(labels == label)[0]
        np.random.shuffle(instance_indices)
        test_ind_start = 0

        added = 0

        for k_ in range(k):
            ntests = nremainings // (k - k_)
            nremainings -= ntests

            kth_fold_instance_indices = instance_indices[test_ind_start: test_ind_start + ntests]

            added += len(kth_fold_instance_indices)
            fold_indices[kth_fold_instance_indices] = k_
            test_ind_start += ntests

        grant_added += added
    return fold_indices


def split_classwise(labels, ratio, nfolds, balanced=False, limits=None):
    """
    Create a training set indices and test set indices such that the k-ratio is preserved for all classes and the number
    of instances per class is within a range
    :param nfolds:
    :param balanced: if True, the number of instances per class is more or less equal
    :param limits: tuple (low-limit = min number of instances per class, high-limit = max number of instances per class)
                   if None, will default to (k, 1.5*k)
    :param labels:
    :param ratio: ratio of the test set over all instances. Must be > 0 and <= 0.5
    :return:
    """
    assert isinstance(labels, np.ndarray) and len(labels.shape) == 1, 'labels must be a 1-D numpy array'
    assert 0. <= ratio <= .5, 'Ratio must be within [0, 0.5]'

    label_sorted_indices = np.argsort(labels)
    sorted_labels = labels[label_sorted_indices]

    uniques, counts = np.unique(sorted_labels, return_counts=True)

    if ratio > 0.:
        assert nfolds <= int(np.floor(1. / ratio + 0.01)), 'Ratio {} doesn\'t permit {} folds'.format(ratio, nfolds)

    if balanced:
        if limits:
            lolimit = limits[0]
            uplimit = limits[1]
        else:
            lolimit = nfolds
            uplimit = int(np.floor(nfolds * 1.5))
    else:
        lolimit = nfolds
        uplimit = None

    if np.any(counts < lolimit):
        if limits:
            raise ValueError(
                'Lower limit of range[{},{}] is too big - there are classes that have less than {} instances'
                .format(lolimit, uplimit, lolimit))
        else:
            raise ValueError('Value of k={} is too big - there are classes that have less than {} instances'
                             .format(nfolds, nfolds))

    nclasses = len(uniques)
    folds = []
    for _ in range(nfolds):
        folds.append(dict(train=[], test=[]))

    for i in range(nclasses):
        if uplimit:
            ninstances = int(min(max(lolimit, counts[i]), uplimit))
        else:
            ninstances = int(max(lolimit, counts[i]))

        nremainings = ninstances
        label = uniques[i]
        instance_indices = np.where(labels == label)[0]
        np.random.shuffle(instance_indices)
        instance_indices = instance_indices[:ninstances]
        test_ind_start = 0

        for k in range(nfolds):
            fold = folds[k]

            ntests = int(np.floor(ninstances * ratio))
            nremainings -= ntests

            fold['test'].append(instance_indices[test_ind_start: test_ind_start + ntests])
            fold['train'].append(
                np.concatenate((instance_indices[0:test_ind_start], instance_indices[test_ind_start + ntests:])))

            test_ind_start += ntests
        assert nremainings >= 0

    for fold in folds:
        fold['test'] = np.concatenate(fold['test'])
        fold['train'] = np.concatenate(fold['train'])

        np.random.shuffle(fold['test'])
        np.random.shuffle(fold['train'])
    return folds


def lcm(x, y):
    if x > y:
        z = x
    else:
        z = y

    while True:
        if z % x == 0 and z % y == 0:
            lcm = z
            break
        z += 1

    return lcm


def divide_conquer(arr, ndivs):
    """
    Divide the array into n equal-length divisions
    If the array length is not divided by n, upsample it to the least common multiple.
    However, if the array is long enough (>= 10n) - divide them unequally is fine
    :param arr:
    :param ndivs:
    :return:
    """
    arr_len = arr.shape[-1]
    need_reshape = arr.ndim == 1
    if need_reshape:
        arr = arr.reshape((1, arr_len))

    arr_proper_len = arr_len if arr_len // ndivs >= 10 else lcm(arr_len, ndivs)

    if arr_len != arr_proper_len:
        multiply_factor = arr_proper_len // arr_len
        new_arr_shape = list(arr.shape)
        new_arr_shape[-1] = arr_proper_len
        new_arr = np.ndarray(new_arr_shape, dtype=arr.dtype)
        for i in range(arr_len):
            for j in range(i * multiply_factor, (i + 1) * multiply_factor):
                new_arr[:, j] = arr[:, i]
    else:
        new_arr = arr

    div_len = arr_proper_len / ndivs
    divs = []
    for i in range(ndivs):
        start = int(np.floor(i * div_len))
        end = int(np.ceil((i + 1) * div_len))
        div = new_arr[:, start:end]
        if need_reshape:
            div = div.ravel()

        divs.append(div)

    return divs


def one_hot(labels):
    """
    Return 1-hot encoded labels.
    E.g. labels = ['A', 'BC', 'D', 'BC'] # 3 classes
         encoded = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 1, 0]]
    :param return_dict: if True also return the lookup dict (label -> encoded)
    :param return_reserved_dict: if True also return the reversed lookup dict (encoded -> label)
    :param labels: a list of labels - can be number or string
    :return:
    """
    unique_labels, enum_labels = np.unique(labels, return_inverse=True)
    num_classes = len(unique_labels)
    one_hot_unique = np.eye(num_classes)
    encoded = np.squeeze(one_hot_unique[enum_labels.reshape(-1)])

    return encoded, unique_labels, enum_labels


def pickle_path(objid, subdir=None, for_url=False):
    fullname = '{}.pkl'.format(objid)
    folder = 'pickle'
    if subdir:
        folder = os.path.join(folder, subdir)
    return data_path(folder, fullname, for_url)


def wav_path(audio_file, for_url=False):
    if audio_file.is_original():
        database_id = str(audio_file.database.id)
        file_name = audio_file.name + '.wav'
    else:
        database_id = str(audio_file.original.database.id)
        file_name = audio_file.original.name + '.wav'
    return data_path('audio/wav/{}'.format(database_id), file_name, for_url)


def audio_path(audio_file, ext, for_url=False):
    if audio_file.is_original():
        database_id = str(audio_file.database.id)
        file_name = audio_file.name + '.' + ext
    else:
        database_id = str(audio_file.original.database.id)
        file_name = audio_file.original.name + '.' + ext
    return data_path('audio/{}/{}'.format(ext, database_id), file_name, for_url)


def history_path(fullname, for_url=False):
    return data_path('history', fullname, for_url)


def spect_fft_path(spect_id, subdir=None, for_url=False):
    folder = 'spect/fft'
    fullname = '{}.png'.format(spect_id)
    if subdir:
        folder = os.path.join(folder, subdir)
    return data_path(folder, fullname, for_url)


def spect_mask_path(spect_id, subdir=None, for_url=False):
    folder = 'spect/mask'
    fullname = '{}.png'.format(spect_id)
    if subdir:
        folder = os.path.join(folder, subdir)
    return data_path(folder, fullname, for_url)
