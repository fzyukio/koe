import numpy as np

from koe.features.utils import unroll_args, get_spectrogram, cached_spectrogram_db


def total_energy(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)

    # This is a little bit unclear. Eq (6.1) of Raven is the calculation below, but then it says it is in decibels,
    # which this is not!
    energy = np.sum(psd) * (fs / nfft)
    return energy


def aggregate_entropy(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)

    # Entropy of energy in each frequency bin over whole time
    ebin = np.sum(psd, axis=1)
    ebin /= np.sum(ebin)
    return np.sum(-ebin * np.log2(ebin))


def average_entropy(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)

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
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psddb = cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap)
    return np.sum(psddb) / np.size(psddb)


def max_power(args):
    """
    Max power is the darkest pixel in the spectrogram
    :param args:
    :return:
    """
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psddb = cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap)
    return np.max(psddb)


def max_frequency(args):
    """
    Max frequency is the frequency at which max power occurs
    :param args:
    :return:
    """
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psddb = cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap)
    max_index = np.argmax(np.max(psddb, axis=1))
    nyquist = fs / 2.0
    return max_index / psddb.shape[0] * nyquist
