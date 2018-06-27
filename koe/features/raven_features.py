import numpy as np

from koe.features.utils import unroll_args, get_psd, get_psddb


def total_energy(args):
    fs, nfft = unroll_args(args, ['fs', 'nfft'])
    psd = get_psd(args)

    # This is a little bit unclear. Eq (6.1) of Raven is the calculation below, but then it says it is in decibels,
    # which this is not!
    energy = np.sum(psd) * (fs / nfft)
    return energy


def aggregate_entropy(args):
    psd = get_psd(args)

    # Entropy of energy in each frequency bin over whole time
    ebin = np.sum(psd, axis=1)
    ebin /= np.sum(ebin)
    return np.sum(-ebin * np.log2(ebin))


def average_entropy(args):
    psd = get_psd(args)

    # Entropy of each frame (time slice) averaged
    newsg = (psd.T / np.sum(psd)).T
    averaged_entropy = np.sum(-newsg * np.log2(newsg), axis=0)
    averaged_entropy = np.mean(averaged_entropy)

    return averaged_entropy


def average_power(args):
    """
    Average power = sum of PSD (in decibel) divided by number of pixels
    :param args:
    :return:
    """
    psddb = get_psddb(args)
    return np.sum(psddb) / np.size(psddb)


def max_power(args):
    """
    Max power is the darkest pixel in the spectrogram
    :param args:
    :return:
    """
    psddb = get_psddb(args)
    return np.max(psddb)


def max_frequency(args):
    """
    Max frequency is the frequency at which max power occurs
    :param args:
    :return:
    """
    psddb = get_psddb(args)
    fs = args['fs']
    max_index = np.argmax(np.max(psddb, axis=1))
    nyquist = fs / 2.0
    return max_index / psddb.shape[0] * nyquist
