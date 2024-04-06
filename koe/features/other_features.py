import numpy as np
from librosa import feature as rosaft

from koe.features.utils import get_psd, get_psddb, get_sig, unroll_args


def frame_entropy(args):
    psd = get_psd(args)

    # Entropy of each frame (time slice) averaged
    newsg = (psd.T / np.sum(psd)).T
    return np.sum(-newsg * np.log2(newsg), axis=0)


def average_frame_power(args):
    """
    Average power = sum of PSD (in decibel) divided by number of pixels
    :param args:
    :return:
    """
    psddb = get_psddb(args)
    return np.mean(psddb, axis=0)


def max_frame_power(args):
    """
    Max power is the darkest pixel in the spectrogram
    :param args:
    :return:
    """
    psddb = get_psddb(args)
    return np.max(psddb, axis=0)


def tonnetz(args):
    sig = get_sig(args)
    fs = args["fs"]
    return rosaft.tonnetz(y=sig, sr=fs)


def chroma_stft(args):
    psd = get_psd(args)
    fs, nfft, noverlap = unroll_args(args, ["fs", "nfft", "noverlap"])
    hopsize = nfft - noverlap
    return rosaft.chroma_stft(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def chroma_cqt(args):
    sig = get_sig(args)
    fs, nfft, noverlap = unroll_args(args, ["fs", "nfft", "noverlap"])
    hopsize = nfft - noverlap
    return rosaft.chroma_cqt(y=sig, sr=fs, hop_length=hopsize)


def chroma_cens(args):
    sig = get_sig(args)
    fs, nfft, noverlap = unroll_args(args, ["fs", "nfft", "noverlap"])
    hopsize = nfft - noverlap
    return rosaft.chroma_cens(y=sig, sr=fs, hop_length=hopsize)
