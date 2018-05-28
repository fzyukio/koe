import numpy as np

from koe.features.utils import unroll_args, get_spectrogram, cached_spectrogram_db


def duration(args):
    # print(inspect.stack()[0][3])
    start, end = unroll_args(args, ['start', 'end'])
    return end - start


def frame_entropy(args):
    # print(inspect.stack()[0][3])
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)

    # Entropy of each frame (time slice) averaged
    newsg = (psd.T / np.sum(psd)).T
    return np.sum(-newsg * np.log2(newsg), axis=0)


def average_frame_power(args):
    """
    Average power = sum of PSD (in decibel) divided by number of pixels
    :param args:
    :return:
    """
    # print(inspect.stack()[0][3])
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psddb = cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap)
    return np.mean(psddb, axis=0)


def max_frame_power(args):
    """
    Max power is the darkest pixel in the spectrogram
    :param args:
    :return:
    """
    # print(inspect.stack()[0][3])
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psddb = cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap)
    return np.max(psddb, axis=0)


def dominant_frequency(args):
    """
    Max frequency is the frequency at which max power occurs
    :param args:
    :return:
    """
    # print(inspect.stack()[0][3])
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psddb = cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap)
    max_indices = np.argmax(psddb, axis=0)
    nyquist = fs / 2.0
    return max_indices / psddb.shape[0] * nyquist
