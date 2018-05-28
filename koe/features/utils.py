import numpy as np
from librosa import stft
from scipy import signal, fft

from koe import wavfile
from koe.utils import segments
from memoize import memoize
from spectrum import dpss


@memoize(timeout=None)
def _cached_get_window(name, nfft):
    assert name in ['hann', 'dpss1', 'dpss2']
    if name == 'hann':
        return signal.get_window('hann', nfft)
    else:
        tapers, eigen = dpss(nfft, 1.5, 2)
        if name == 'dpss1':
            return tapers[:, 0]
        else:
            return tapers[:, 1]


@memoize(timeout=60)
def cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, window_name):
    fs, chunk_, _ = wavfile.read(wav_file_path, start, end, normalised=True, mono=False)

    window = _cached_get_window(window_name, nfft)
    hopsize = win_length - noverlap
    return stft(y=chunk_, n_fft=nfft, win_length=win_length, hop_length=hopsize, window=window, center=False,
                dtype=np.complex128)


def get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, win_length):
    spect__ = cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, window_name='hann')

    return np.abs(spect__)


def cached_spectrogram_db(wav_file_path, fs, start, end, nfft, noverlap):
    spect = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)

    return np.log10(spect) * 10.0


def unroll_args(args, requires):
    retval = []
    for require in requires:
        val = args[require]
        retval.append(val)
    return tuple(retval)


def my_stft(sig, fs, window, noverlap, nfft):
    siglen = len(sig)
    freq_range = nfft // 2 + 1
    window_size = len(window)
    nsegs, segs = segments(siglen, window_size, noverlap, incltail=False)
    mat = np.ndarray((freq_range, nsegs), dtype=np.complex128)
    for i in range(nsegs):
        seg = segs[i, :]
        subsig = sig[seg[0]: seg[1]]
        spectrum = fft(subsig * window, nfft)
        mat[:, i] = spectrum[:freq_range]
    return mat
