from librosa import feature as rosaft

from koe.features.utils import unroll_args, psd_or_sig, get_sig


def spectral_flatness(args):
    psd, sig = psd_or_sig(args)
    nfft, noverlap = unroll_args(args, ['nfft', 'noverlap'])
    hopsize = nfft - noverlap

    return rosaft.spectral_flatness(y=sig, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_bandwidth(args):
    psd, sig = psd_or_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_bandwidth(y=sig, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_centroid(args):
    psd, sig = psd_or_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_centroid(y=sig, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_contrast(args):
    psd, sig = psd_or_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_contrast(y=sig, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def spectral_rolloff(args):
    psd, sig = psd_or_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.spectral_rolloff(y=sig, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def chroma_stft(args):
    psd, sig = psd_or_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.chroma_stft(y=sig, sr=fs, S=psd, n_fft=nfft, hop_length=hopsize)


def chroma_cqt(args):
    sig = get_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.chroma_cqt(y=sig, sr=fs, hop_length=hopsize)


def chroma_cens(args):
    sig = get_sig(args)
    fs, nfft, noverlap = unroll_args(args, ['fs', 'nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.chroma_cens(y=sig, sr=fs, hop_length=hopsize)


def mfcc(args):
    sig = get_sig(args)
    fs = args['fs']
    return rosaft.mfcc(y=sig, sr=fs, S=None, n_mfcc=26)


def zero_crossing_rate(args):
    sig = get_sig(args)
    nfft, noverlap = unroll_args(args, ['nfft', 'noverlap'])
    hopsize = nfft - noverlap
    return rosaft.zero_crossing_rate(y=sig, frame_length=2048, hop_length=hopsize)


def tonnetz(args):
    sig = get_sig(args)
    fs = args['fs']
    return rosaft.tonnetz(y=sig, sr=fs)
