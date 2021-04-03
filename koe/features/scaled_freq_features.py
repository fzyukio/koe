import numpy as np
from librosa import filters
from librosa import power_to_db
from memoize import memoize

from koe.features.utils import unroll_args, get_psd


def dct(n_filters, n_input):
    """
    Copied from librosa.filters as it is deprecated from 0.7.0
    """

    basis = np.empty((n_filters, n_input))
    basis[0, :] = 1.0 / np.sqrt(n_input)

    samples = np.arange(1, 2*n_input, 2) * np.pi / (2.0 * n_input)

    for i in range(1, n_filters):
        basis[i, :] = np.cos(i*samples) * np.sqrt(2.0/n_input)

    return basis


@memoize(timeout=60 * 60 * 24)
def _cached_get_mel_filter(sr, n_fft, n_mels, fmin, fmax):
    return filters.mel(sr=sr, n_fft=n_fft, n_mels=n_mels, fmin=fmin, fmax=fmax)


def mfc(args):
    psd = get_psd(args) ** 2
    fs, nfft, ncep, fmin, fmax = unroll_args(args, ['fs', 'nfft', ('ncep', 20), ('fmin', 0.0), ('fmax', None)])
    if fmax is None:
        fmax = fs // 2

    # Build a Mel filter
    mel_basis = _cached_get_mel_filter(sr=fs, n_fft=nfft, n_mels=ncep * 2, fmin=fmin, fmax=fmax)
    melspect = np.dot(mel_basis, psd)
    return power_to_db(melspect)


def mfcc(args):
    ncep = unroll_args(args, [('ncep', 20)])
    S = mfc(args)
    librosa_dct = dct(ncep, S.shape[0])
    return np.dot(librosa_dct, S)


def mfcc_delta(args):
    cc = mfcc(args)
    diff = np.pad(np.diff(cc), ((0, 0), (1, 0)), 'constant', constant_values=0)
    return diff


def mfcc_delta2(args):
    cc = mfc(args)
    diff = np.pad(np.diff(cc), ((0, 0), (1, 0)), 'constant', constant_values=0)
    return diff
