from librosa import feature as rosaft

from koe import wavfile
from koe.features.utils import unroll_args, get_spectrogram


def spectral_flatness(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)
    hopsize = nfft - noverlap
    return rosaft.spectral_flatness(y=None, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_bandwidth(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)
    hopsize = nfft - noverlap

    return rosaft.spectral_bandwidth(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_centroid(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)
    hopsize = nfft - noverlap
    return rosaft.spectral_centroid(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_contrast(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)
    hopsize = nfft - noverlap
    return rosaft.spectral_contrast(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_rolloff(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)
    hopsize = nfft - noverlap
    return rosaft.spectral_rolloff(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def chroma_stft(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])

    psd = get_spectrogram(wav_file_path, fs, start, end, nfft, noverlap, nfft)
    hopsize = nfft - noverlap
    return rosaft.chroma_stft(y=None, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def chroma_cqt(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])
    sig = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True)
    hopsize = nfft - noverlap
    return rosaft.chroma_cqt(y=sig, sr=fs, hop_length=hopsize)


def chroma_cens(args):
    wav_file_path, fs, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end', 'nfft', 'noverlap'])
    sig = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True)
    hopsize = nfft - noverlap
    return rosaft.chroma_cens(y=sig, sr=fs, hop_length=hopsize)


def mfcc(args):
    wav_file_path, fs, start, end = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end'])
    chunk = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True)

    return rosaft.mfcc(y=chunk, sr=fs, S=None, n_mfcc=26)


def zero_crossing_rate(args):
    wav_file_path, start, end, nfft, noverlap = \
        unroll_args(args, ['wav_file_path', 'start', 'end', 'nfft', 'noverlap'])

    sig = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True)
    hopsize = nfft - noverlap
    return rosaft.zero_crossing_rate(y=sig, frame_length=2048, hop_length=hopsize)


def tonnetz(args):
    wav_file_path, fs, start, end = \
        unroll_args(args, ['wav_file_path', 'fs', 'start', 'end'])

    sig = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=True)

    return rosaft.tonnetz(y=sig, sr=fs)
