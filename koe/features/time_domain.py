import numpy as np
from librosa import feature as rosaft

from koe.features.utils import _cached_get_window, get_sig, unroll_args


def duration(args):
    start, end = unroll_args(args, ["start", "end"])
    retval = np.ndarray((1, 1), dtype=np.float32)
    retval[0] = end - start
    return retval


def zero_crossing_rate(args):
    sig = get_sig(args)
    nfft, noverlap = unroll_args(args, ["nfft", "noverlap"])
    hopsize = nfft - noverlap
    zcr = rosaft.zero_crossing_rate(y=sig, frame_length=nfft, hop_length=hopsize, center=False)
    return zcr


def time_axis(args):
    sig = get_sig(args)
    fs = unroll_args(args, ["fs"])
    length = len(sig)
    t_end_sec = length / fs
    time = np.linspace(0, t_end_sec, length)
    return time


def log_attack_time(args):
    envelope = energy_envelope(args)
    stop_pos = np.argmax(envelope)
    stop_val = envelope[stop_pos]

    threshold_percent = 2

    threshold = stop_val * threshold_percent / 100
    tmp = np.where(envelope > threshold)[0]
    start_pos = tmp[0]
    if start_pos == stop_pos:
        start_pos -= 1

    time = time_axis(args)
    lat = np.ndarray((1, 1), dtype=np.float32)
    lat[0] = np.log10((time[stop_pos] - time[start_pos]))
    return lat


def energy_envelope(args):
    sig = get_sig(args)
    nfft = unroll_args(args, ["nfft"])
    sig = np.abs(sig)
    hann_window = _cached_get_window("hanning", nfft)
    envelope = np.convolve(sig, hann_window, "same")
    return envelope


def temporal_centroid(args):
    envelope = energy_envelope(args)
    time = time_axis(args)

    tc = np.sum(envelope * time) / np.sum(envelope)
    return tc
