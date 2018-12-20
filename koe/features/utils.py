import numpy as np
from librosa import stft
from scipy import signal, fft

from koe import wavfile
from koe.utils import segments
from memoize import memoize
from spectrum import dpss


@memoize(timeout=None)
def _cached_get_window(name, nfft):
    if name.startswith('dpss'):
        assert name in ['dpss1', 'dpss2']
        type = int(name[4:]) - 1
        tapers, eigen = dpss(nfft, 1.5, 2)
        return tapers[:, type]

    else:
        return signal.get_window(name, nfft)


# @profile
def stft_from_sig(sig, nfft, noverlap, win_length, window_name, center):
    window = _cached_get_window(window_name, nfft)
    hopsize = win_length - noverlap
    center |= len(sig) < win_length

    return stft(y=sig, n_fft=nfft, win_length=win_length, hop_length=hopsize, window=window, center=center,
                dtype=np.complex128)


# @profile
def get_psd(args):
    wav_file_path, fs, start, end, nfft, noverlap, win_length, center = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap', 'win_length', 'center'])

    if wav_file_path:
        psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft, center)
    else:
        sig = args['sig']
        psd = np.abs(stft_from_sig(sig, nfft, noverlap, win_length, 'hann', center))
    return psd


# @profile
def get_sig(args):
    wav_file_path, fs, start, end = unroll_args(args, ['wav_file_path', 'fs', 'start', 'end'])
    if wav_file_path:
        sig = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True)
    else:
        sig = args['sig']
    return sig


# @profile
def maybe_cached_stft(args, window_name):
    wav_file_path, fs, start, end, nfft, noverlap, win_length, center = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap', 'win_length', 'center'])
    if wav_file_path:
        tapered = cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, window_name, center)
    else:
        sig = args['sig']
        tapered = stft_from_sig(sig, nfft, noverlap, win_length, window_name, center)

    return tapered


# @profile
def get_psddb(args):
    spect = get_psd(args)
    return np.log10(spect) * 10.0


# @memoize(timeout=60)
# @profile
def cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, window_name, center):
    fs, chunk, _ = wavfile.read(wav_file_path, start, end, normalised=True, mono=True)
    return stft_from_sig(chunk, nfft, noverlap, win_length, window_name, center)


# @profile
def get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, win_length, center):
    spect__ = cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, 'hann', center)

    return np.abs(spect__)


# @profile
def unroll_args(args, requires):
    retval = []
    for require in requires:
        if isinstance(require, tuple):
            val = args.get(require[0], require[1])
        else:
            val = args[require]
        retval.append(val)
    if len(requires) > 1:
        return tuple(retval)
    return val


# @profile
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
