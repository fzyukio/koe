import contextlib

import numpy as np
from scipy import signal
from scipy.cluster.hierarchy import linkage
from scipy.signal import fftconvolve
from scipy.spatial.distance import pdist


def normxcorr2(template, image, mode="valid"):
    """
    Input arrays should be floating point numbers.
    :param template: N-D array, of template or filter you are using for cross-correlation.
    Must be less or equal dimensions to image.
    Length of each dimension must be less than length of image.
    :param image: N-D array
    :param mode: Options, "full", "valid", "same"
    full (Default): The output of fftconvolve is the full discrete linear convolution of the inputs.
    Output size will be image size + 1/2 template size in each dimension.
    valid: The output consists only of those elements that do not rely on the zero-padding.
    same: The output is the same size as image, centered with respect to the ‘full’ output.
    :return: N-D array of same dimensions as image. Size depends on mode parameter.
    :author: Ujash Joshi, University of Toronto, 2017. Downloaded from
             https://raw.githubusercontent.com/Sabrewarrior/normxcorr2-python/master/normxcorr2.py
    """

    # If this happens, it is probably a mistake
    if np.ndim(template) > np.ndim(image) or \
                    len([i for i in range(np.ndim(template)) if template.shape[i] > image.shape[i]]) > 0:
        print("normxcorr2: TEMPLATE larger than IMG. Arguments may be swapped.")

    template -= np.mean(template)
    image -= np.mean(image)

    a1 = np.ones(template.shape)
    # Faster to flip up down and left right then use fftconvolve instead of scipy's correlate
    ar = np.flipud(np.fliplr(template))
    out = fftconvolve(image, ar.conj(), mode=mode)

    image = fftconvolve(np.square(image), a1, mode=mode) - \
            np.square(fftconvolve(image, a1, mode=mode)) / (np.prod(template.shape))

    # Remove small machine precision errors after subtraction
    image[np.where(image < 0)] = 0

    template = np.sum(np.square(template))
    out = out / np.sqrt(image * template)

    # Remove any divisions by 0 or very close to 0
    out[np.where(np.logical_not(np.isfinite(out)))] = 0

    return out


def vco(farray, fs, fmin=0, fmax=None):
    """
    Voltage controlled oscillator. Creates a signal which oscillates at a frequency determined by the input vector
    farray
    :param farray: a one dimensional np.array, values are instantaneous frequency in Hz at time t
    :param fs: sampling rate
    :param fmin: minimum frequency in Hz. Default to 0
    :param fmax: maximum frequency in Hz. Default to nyquist
    :return: a np.array of the frequency modulated signal
    """
    assert len(farray.shape) == 1, 'farray must be one-dimensional'
    assert min(farray) >= -1 and max(farray) <= 1, 'farray must be in within range [-1, 1]'

    nyquist = fs / 2
    x = farray.astype(np.float) / nyquist
    min_x1 = min(x)
    max_x1 = max(x)

    x = (x - min_x1 - max_x1) / max_x1

    if fmax is None:
        fmax = fs / 2

    fc = (fmin + fmax) / 2
    range = (fmax - fc) / nyquist * 2 * np.pi

    length = x.shape[0]
    t = np.arange(0, (length / fs), 1 / fs)
    y = np.cos(2 * np.pi * (2 * fc) * t + range * np.cumsum(x))

    return y


@contextlib.contextmanager
def printoptions(*args, **kwargs):
    original = np.get_printoptions()
    np.set_printoptions(*args, **kwargs)
    try:
        yield
    finally:
        np.set_printoptions(**original)


if __name__ == '__main__':
    def test_normxcorr2():
        b = np.array([[8, 1, 6], [3, 5, 7], [4, 9, 2]], dtype=np.float64)
        a = np.array([[8, 1, 6, 8, 5], [3, 5, 7, 4, 6], [4, 9, 2, 0, 2], [0, 2, 9, 1, 3], [1, 8, 5, 2, 9]],
                     dtype=np.float64)

        c = normxcorr2(b, a)
        with printoptions(precision=3, suppress=True):
            print(c)

    def test_vco():
        import pylab as pl

        length_ms = 20000
        fs = 20000
        nyquist = fs / 2
        window_size = 512
        window = signal.get_window('hann', window_size)
        noverlap = window_size * 0.75
        nfft = window_size
        scale = window.sum()

        f0_min = 100
        f0_max = 9900

        ts = 1 / fs
        nsamples = length_ms / 1000 / ts
        t = np.arange(1, nsamples + 1) * ts
        f0_up_log = np.logspace(np.log10(f0_min), np.log10(f0_max), nsamples)

        pl.subplot(311)
        pl.plot(t, f0_up_log)

        sig = vco(f0_up_log, fs)
        pl.subplot(312)
        pl.plot(t, sig)

        f, t, s = signal.stft(sig, fs=fs, window=window, noverlap=noverlap, nfft=nfft, nperseg=window_size,
                              return_onesided=True)
        p = np.abs(s * scale)
        pl.subplot(313)

        pl.pcolormesh(t, f, 20 * np.log10(p), cmap='jet')

        pl.show()

    def test_pdist(n):
        import datetime
        ns = 22000 // n
        arr = np.random.rand(n, 3)
        start = datetime.datetime.now()
        y = None
        for i in range(ns):
            y = linkage(arr, method='average')
        end = datetime.datetime.now()
        memory = y.nbytes
        elapsed = (end - start).total_seconds() * 1000 / ns
        print('N={}, Time={}, Memory={}'.format(n, elapsed, memory))

    # test_vco()
    test_pdist(22000)
