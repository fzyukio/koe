"""
General utils for the entire project.
DO NOT import any project-related files here. NO Model, NO form, NO nothing.
model_utils is there you can import those
"""
import base64
import contextlib
import re
import wave

import numpy as np
from scipy.signal import fftconvolve


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


########################################################################################
# Author: Ujash Joshi, University of Toronto, 2017                                     #
# Based on Octave implementation by: Benjamin Eltzner, 2014 <b.eltzner@gmx.de>         #
# Octave/Matlab normxcorr2 implementation in python 3.5                                #
# Details:                                                                             #
# Normalized cross-correlation. Similiar results upto 3 significant digits.            #
# https://github.com/Sabrewarrior/normxcorr2-python/master/norxcorr2.py                #
# http://lordsabre.blogspot.ca/2017/09/matlab-normxcorr2-implemented-in-python.html    #
########################################################################################


def normxcorr2(template, image, mode="valid"):
    """
    Input arrays should be floating point numbers.
    :param template: N-D array, of template or filter you are using for cross-correlation.
    Must be less or equal dimensions to image.
    Length of each dimension must be less than length of image.
    :param image: N-D array
    :param mode: Options, "full", "valid", "same"
    full (Default): The output of fftconvolve is the full discrete linear convolution of the inputs.
    Output size will be image size + 1/2 template size in each dimension.
    valid: The output consists only of those elements that do not rely on the zero-padding.
    same: The output is the same size as image, centered with respect to the ‘full’ output.
    :return: N-D array of same dimensions as image. Size depends on mode parameter.
    """
    # If this happens, it is probably a mistake
    if np.ndim(template) > np.ndim(image) or \
            len([i for i in range(np.ndim(template)) if template.shape[i] > image.shape[i]]) > 0:
        print("normxcorr2: TEMPLATE larger than IMG. Arguments may be swapped.")

    template -= np.mean(template)
    image -= np.mean(image)

    a1 = np.ones(template.shape)
    # Faster to flip up down and left right then use fftconvolve instead of scipy's correlate
    ar = np.flipud(np.fliplr(template))
    out = fftconvolve(image, ar.conj(), mode=mode)

    image = fftconvolve(np.square(image), a1, mode=mode) \
        - np.square(fftconvolve(image, a1, mode=mode)) / (np.prod(template.shape))

    # Remove small machine precision errors after subtraction
    image[np.where(image < 0)] = 0

    template = np.sum(np.square(template))
    out = out / np.sqrt(image * template)

    # Remove any divisions by 0 or very close to 0
    out[np.where(np.logical_not(np.isfinite(out)))] = 0

    return out


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
