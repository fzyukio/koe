import os
import pickle

import numpy as np
from PIL import Image

from koe import wavfile
from koe.colourmap import cm_green
from koe.colourmap import cm_red, cm_blue
from koe.features.scaled_freq_features import mfcc
from koe.features.utils import get_spectrogram

nfft = 512
noverlap = nfft // 2
win_length = nfft
stepsize = nfft - noverlap


def extract_spect(wav_file_path, fs, start, end, filepath=None):
    value = get_spectrogram(wav_file_path, fs=fs, start=start, end=end, nfft=nfft, noverlap=noverlap, win_length=nfft,
                            center=False)

    if filepath:
        with open(filepath, 'wb') as f:
            pickle.dump(value, f)
    else:
        return value


def extract_mfcc(wav_file_path, fs, start, end, filepath=None):
    sig = wavfile.read_segment(wav_file_path, beg_ms=start, end_ms=end, mono=True)
    args = dict(nfft=nfft, noverlap=noverlap, win_length=win_length, fs=fs, wav_file_path=None, start=0, end=None,
                sig=sig, center=True)
    value = mfcc(args)

    if filepath:
        with open(filepath, 'wb') as f:
            pickle.dump(value, f)
    else:
        return value


def extract_log_spect(wav_file_path, fs, start, end, filepath=None):
    psd = get_spectrogram(wav_file_path, fs=fs, start=start, end=end, nfft=nfft, noverlap=noverlap, win_length=nfft,
                          center=False)
    eps = 1e-3
    # find maximum
    psd_abs = abs(psd)
    psd_max = psd_abs.max()
    # compute 20*log magnitude, scaled to the max
    value = 20.0 * np.log10(psd_abs / psd_max + eps)

    if filepath:
        with open(filepath, 'wb') as f:
            pickle.dump(value, f)
    else:
        return value

eps = 1e-3


def psd2img(psd, imgpath, islog=False):
    """
    Extract raw sepectrograms for all segments (Not the masked spectrogram from Luscinia) of an audio file
    :param audio_file:
    :return:
    """
    height, width = np.shape(psd)
    psd = np.flipud(psd)

    if not islog:
        # find maximum
        psd_max = abs(psd).max()
        # compute 20*log magnitude, scaled to the max
        psd = 20.0 * np.log10(abs(psd) / psd_max + eps)

    min_spect_pixel = psd.min()
    max_spect_pixel = psd.max()
    spect_pixel_range = max_spect_pixel - min_spect_pixel
    interval64 = spect_pixel_range / 63

    psd = ((psd - min_spect_pixel) / interval64)
    psd[np.isinf(psd)] = 0
    psd = psd.astype(np.int)

    psd = psd.reshape((width * height,), order='C')
    psd[psd >= 64] = 63
    # psd[psd < 64] = 0
    psd_rgb = np.empty((height, width, 3), dtype=np.uint8)
    psd_rgb[:, :, 0] = cm_red[psd].reshape((height, width)) * 255
    psd_rgb[:, :, 1] = cm_green[psd].reshape((height, width)) * 255
    psd_rgb[:, :, 2] = cm_blue[psd].reshape((height, width)) * 255
    img = Image.fromarray(psd_rgb)
    img.save(imgpath, format='PNG')


def extract_global_min_max(folder, format):
    ext = '.{}'.format(format)
    mins = []
    maxs = []
    for filename in os.listdir(folder):
        if filename.lower().endswith(ext):
            file_path = os.path.join(folder, filename)
            with open(file_path, 'rb') as f:
                spect = pickle.load(f)
                mins.append(np.min(spect, axis=1))
                maxs.append(np.max(spect, axis=1))
    global_min = np.min(mins, axis=0).reshape([-1, 1])
    global_max = np.max(maxs, axis=0).reshape([-1, 1])

    return global_min, global_max


def save_global_min_max(norm_folder, global_min, global_max):
    global_min_file_path = os.path.join(norm_folder, 'global_min')
    with open(global_min_file_path, 'wb') as f:
        pickle.dump(global_min, f)

    global_max_file_path = os.path.join(norm_folder, 'global_max')
    with open(global_max_file_path, 'wb') as f:
        pickle.dump(global_max, f)


def load_global_min_max(min_max_loc):
    global_min_file_path = os.path.join(min_max_loc, 'global_min')
    with open(global_min_file_path, 'rb') as f:
        global_min = pickle.load(f)

    global_max_file_path = os.path.join(min_max_loc, 'global_max')
    with open(global_max_file_path, 'rb') as f:
        global_max = pickle.load(f)

    return global_min, global_max


def normalise_all(folder, norm_folder, format, global_min, global_max):
    ext = '.{}'.format(format)
    global_range = global_max - global_min
    for filename in os.listdir(folder):
        if filename.lower().endswith(ext):
            file_path = os.path.join(folder, filename)
            file_norm_path = os.path.join(norm_folder, filename)
            with open(file_path, 'rb') as f:
                spect = pickle.load(f)
            spect = (spect - global_min) / global_range
            with open(file_norm_path, 'wb') as f:
                pickle.dump(spect, f)


extractors = {
    'spect': extract_spect,
    'mfcc': extract_mfcc,
    'log_spect': extract_log_spect
}
