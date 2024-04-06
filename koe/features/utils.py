import numpy as np
from librosa import stft
from memoize import memoize
from scipy import fft, signal
from spectrum import dpss

from koe import wavfile
from koe.utils import split_segments


@memoize(timeout=None)
def _cached_butter_bandpass(lpf, hpf, fs):
    nyquist = fs // 2
    if lpf is None:
        lpf = nyquist
    if hpf is None:
        hpf = 0

    if lpf == nyquist and hpf == 0:
        return None

    band = 50

    if lpf == nyquist:
        # High pass filter
        cut1 = hpf / nyquist
        cut2 = (hpf + band) / nyquist
        # calculate the best order
        order, wN = signal.buttord(cut1, cut2, 3, band)
        btype = "highpass"

    elif hpf == 0:
        # # Low pass filter
        cut1 = lpf / nyquist
        cut2 = (lpf - band) / nyquist
        # # calculate the best order
        order, wN = signal.buttord(cut1, cut2, 3, band)
        btype = "lowpass"

    else:
        high = hpf / nyquist
        high_cut = (hpf + band) / nyquist
        low = lpf / nyquist
        low_cut = (lpf - band) / nyquist
        # # calculate the best order
        order, wN = signal.buttord([low, low_cut], [high, high_cut], 3, band)
        btype = "bandpass"

    order = min(10, order)
    return signal.butter(order, wN, btype=btype)


def butter_bandpass_filter(data, lpf, hpf, fs):
    filter_args = _cached_butter_bandpass(lpf, hpf, fs)
    if filter_args is None:
        # No need to filter
        return data

    b, a = filter_args
    return signal.filtfilt(b, a, data)


@memoize(timeout=None)
def _cached_get_window(name, nfft):
    if name.startswith("dpss"):
        assert name in ["dpss1", "dpss2"]
        type = int(name[4:]) - 1
        tapers, eigen = dpss(nfft, 1.5, 2)
        return tapers[:, type]

    else:
        return signal.get_window(name, nfft)


def stft_from_sig(sig, nfft, noverlap, win_length, window_name, center):
    window = _cached_get_window(window_name, nfft)
    hopsize = win_length - noverlap
    center |= len(sig) < win_length

    return stft(
        y=sig,
        n_fft=nfft,
        win_length=win_length,
        hop_length=hopsize,
        window=window,
        center=center,
        dtype=np.complex128,
    )


def get_psd(args):
    wav_file_path, fs, start, end, nfft, noverlap, win_length, center = unroll_args(
        args,
        [
            "wav_file_path",
            "fs",
            "start",
            "end",
            "nfft",
            "noverlap",
            "win_length",
            "center",
        ],
    )

    if wav_file_path:
        psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft, center)
    else:
        sig = args["sig"]
        psd = np.abs(stft_from_sig(sig, nfft, noverlap, win_length, "hann", center))
    return psd


def get_sig(args):
    wav_file_path, fs, start, end, win_length, lpf, hpf = unroll_args(
        args, ["wav_file_path", "fs", "start", "end", "win_length", "lpf", "hpf"]
    )

    if wav_file_path:
        sig = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True, winlen=win_length)
    else:
        sig = args["sig"]

    return butter_bandpass_filter(sig, lpf, hpf, fs)


def maybe_cached_stft(args, window_name):
    wav_file_path, fs, start, end, nfft, noverlap, win_length, center = unroll_args(
        args,
        [
            "wav_file_path",
            "fs",
            "start",
            "end",
            "nfft",
            "noverlap",
            "win_length",
            "center",
        ],
    )
    if wav_file_path:
        tapered = cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, window_name, center)
    else:
        sig = args["sig"]
        tapered = stft_from_sig(sig, nfft, noverlap, win_length, window_name, center)

    return tapered


def get_psddb(args):
    spect = get_psd(args)
    return np.log10(spect) * 10.0


# @memoize(timeout=60)
def cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, window_name, center):
    chunk, fs = wavfile.read_segment(wav_file_path, start, end, normalised=True, mono=True, return_fs=True)
    return stft_from_sig(chunk, nfft, noverlap, win_length, window_name, center)


def get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, win_length, center):
    spect__ = cached_stft(wav_file_path, start, end, nfft, noverlap, win_length, "hann", center)

    return np.abs(spect__)


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


def my_stft(sig, fs, window, noverlap, nfft):
    siglen = len(sig)
    freq_range = nfft // 2 + 1
    window_size = len(window)
    nsegs, segs = split_segments(siglen, window_size, noverlap, incltail=False)
    mat = np.ndarray((freq_range, nsegs), dtype=np.complex128)
    for i in range(nsegs):
        seg = segs[i]
        subsig = sig[seg[0] : seg[1]]
        spectrum = fft(subsig * window, nfft)
        mat[:, i] = spectrum[:freq_range]
    return mat
