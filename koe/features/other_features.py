import numpy as np

from koe.features.utils import unroll_args, get_psddb, get_psd


def duration(args):
    start, end = unroll_args(args, ['start', 'end'])
    return end - start


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


def dominant_frequency(args):
    """
    Max frequency is the frequency at which max power occurs
    :param args:
    :return:
    """
    psddb = get_psddb(args)
    fs = args['fs']
    max_indices = np.argmax(psddb, axis=0)
    nyquist = fs / 2.0
    return max_indices / psddb.shape[0] * nyquist
