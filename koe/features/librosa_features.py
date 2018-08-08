import numpy as np
from librosa import feature as rosaft, power_to_db
from librosa import filters
from memoize import memoize

from koe.features.utils import unroll_args, get_psd, get_sig


@memoize(timeout=60 * 60 * 24)
def _cached_get_mel_filter(sr, n_fft, n_mels):
    return filters.mel(sr=sr, n_fft=n_fft, n_mels=n_mels)


# @profile
def spectral_flatness(args):
    psd = get_psd(args)
    nfft, noverlap = unroll_args(args, ['nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_flatness(y=None, S=psd, n_fft=nfft, hop_length=hopsize)


# @profile
def spectral_bandwidth(args):
    psd = get_psd(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_bandwidth(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


# @profile
def spectral_centroid(args):
    psd = get_psd(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_centroid(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


# @profile
def spectral_contrast(args):
    psd = get_psd(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_contrast(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


# @profile
def spectral_rolloff(args):
    psd = get_psd(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_rolloff(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


# @profile
def chroma_stft(args):
    psd = get_psd(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.chroma_stft(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


# @profile
def chroma_cqt(args):
    sig = get_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.chroma_cqt(y=sig, sr=fs, hop_length=hopsize)


# @profile
def chroma_cens(args):
    sig = get_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.chroma_cens(y=sig, sr=fs, hop_length=hopsize)


# @profile
def mfcc(args):
    psd = get_psd(args) ** 2
    fs, nfft = unroll_args(args, ['fs', 'nfft'])

    # Build a Mel filter
    mel_basis = _cached_get_mel_filter(sr=fs, n_fft=nfft, n_mels=128)
    melspect = np.dot(mel_basis, psd)
    S = power_to_db(melspect)
    return np.dot(filters.dct(20, S.shape[0]), S)


# @profile
def zero_crossing_rate(args):
    sig = get_sig(args)
    nfft, noverlap = unroll_args(args, ['nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.zero_crossing_rate(y=sig, frame_length=nfft, hop_length=hopsize, center=False)


# @profile
def tonnetz(args):
    sig = get_sig(args)
    fs = args['fs']
    return rosaft.tonnetz(y=sig, sr=fs)
