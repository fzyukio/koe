import numpy as np
from librosa import filters
from librosa import power_to_db

from koe.features.utils import unroll_args, get_psd
from memoize import memoize


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
    return np.dot(filters.dct(ncep, S.shape[0]), S)


def mfcc_delta(args):
    cc = mfcc(args)
    diff = np.pad(np.diff(cc), ((0, 0), (1, 0)), 'constant', constant_values=0)
    return diff


def mfcc_delta2(args):
    cc = mfc(args)
    diff = np.pad(np.diff(cc), ((0, 0), (1, 0)), 'constant', constant_values=0)
    return diff
