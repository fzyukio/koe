import numpy as np
from scipy.fftpack import ifft
from skimage.measure import label
from skimage.measure import regionprops

from koe.features.utils import unroll_args, maybe_cached_stft


def find_zc(arr):
    v_ = arr * np.roll(arr, 1, 0)
    return np.where((v_ < 0) & (arr < 0))


# @memoize(timeout=60)
def cached_tf_derivatives(args):
    tapered1 = maybe_cached_stft(args, 'dpss1')
    tapered2 = maybe_cached_stft(args, 'dpss2')

    real1 = np.real(tapered1)
    real2 = np.real(tapered2)
    imag1 = np.imag(tapered1)
    imag2 = np.imag(tapered2)

    time_deriv = (-real1 * real2) - (imag1 * imag2)
    freq_deriv = (imag1 * real2) - (real1 * imag2)

    return time_deriv, freq_deriv


# @profile
def time_derivative(args):
    time_deriv, _ = cached_tf_derivatives(args)
    return time_deriv


# @profile
def freq_derivative(args):
    _, freq_deriv = cached_tf_derivatives(args)
    return freq_deriv


# @profile
def frequency_modulation(args):
    time_deriv, freq_deriv = cached_tf_derivatives(args)
    return np.arctan(np.max(time_deriv, axis=0) / (np.max(freq_deriv, axis=0) + 0.1))


# @profile
def amplitude_modulation(args):
    time_deriv, _ = cached_tf_derivatives(args)
    return np.sum(time_deriv, axis=0)


# @profile
def goodness_of_pitch(args):
    nfft = args['nfft']
    stft = maybe_cached_stft(args, 'dpss1')

    # To restore the full spectrum, we should've conjugated the second half.
    # e.g. np.concatenate((stft, np.conj(stft[-2:0:-1, :])), axis=0)
    # But since the next line takes the absolute value of the spectrum - it doesn't matter.
    full_stft = np.concatenate((stft, stft[-2:0:-1, :]), axis=0)
    tmp = ifft(np.log(np.abs(full_stft)), axis=0)
    tmp = tmp.real[24:nfft // 2 + 1]
    return np.max(tmp, axis=0)


# @profile
def mtspect(args):
    tapered1 = maybe_cached_stft(args, 'dpss1')
    tapered2 = maybe_cached_stft(args, 'dpss2')
    return (np.abs(tapered1) ** 2 + np.abs(tapered2) ** 2) / 2


# @profile
def amplitude(args):
    s = mtspect(args)
    m_LogSum = np.sum(s[3:, :], axis=0)
    return 10 * (np.log10(m_LogSum))


# @profile
def entropy(args):
    s = mtspect(args)
    mean_log = np.mean(np.log(s[3:, :]), axis=0)
    log_mean = np.log(np.mean(s[3:, :], axis=0))
    return mean_log - log_mean


# @profile
def spectral_continuity(args):
    contours = frequency_contours(args)
    label_img = label(contours, connectivity=contours.ndim)
    props = regionprops(label_img)

    connection_mask = np.zeros(contours.shape, dtype=np.int32)
    continuity = np.zeros(contours.shape)

    for p in props:
        coords = p.coords
        y = coords[:, 0]
        x = coords[:, 1]

        num_pixels = len(coords)
        range_time = np.max(x) - np.min(x)
        continuity[(y, x)] = range_time
        if num_pixels > 5:
            connection_mask[(y, x)] = num_pixels
        else:
            connection_mask[(y, x)] = 0

    max_row_idx = np.argmax(connection_mask, axis=0)
    max_col_idx = np.arange(0, connection_mask.shape[1])

    max_continuity = connection_mask[(max_row_idx, max_col_idx)]

    continuity_at_max = continuity[(max_row_idx, max_col_idx)]
    continuity_frame = (continuity_at_max / max_continuity) * 100
    continuity_frame[np.where(np.isnan(continuity_frame))] = 0

    return continuity_frame


# @profile
def frequency_contours(args):
    derivs = spectral_derivative(args)
    derivs_abs = np.abs(derivs)

    row_thresh = 0.3 * np.mean(derivs_abs, axis=0)
    col_thresh = 100 * np.median(derivs_abs, axis=1)

    mask_row = derivs_abs <= row_thresh[None, :]
    mask_col = derivs_abs <= col_thresh[:, None]
    mask = (mask_row | mask_col)
    derivs[mask] = -0.1

    zcy, zcx = find_zc(derivs)
    contours = np.full(derivs.shape, False, dtype=np.bool)
    contours[zcy, zcx] = True

    return contours


# @profile
def mean_frequency(args):
    fs, nfft = unroll_args(args, ['fs', 'nfft'])
    s = mtspect(args)
    freq_range = nfft // 2 + 1
    idx = np.arange(freq_range)
    tmp = s * idx.reshape((freq_range, 1))
    x = np.sum(tmp, axis=0) / np.sum(s, axis=0) * fs / nfft
    return x


# @profile
def spectral_derivative(args):
    time_deriv, freq_deriv = cached_tf_derivatives(args)
    fm = frequency_modulation(args)

    cfm = np.cos(fm)
    sfm = np.sin(fm)
    spectral_deriv = (time_deriv * sfm + freq_deriv * cfm)

    spectral_deriv[0:3, :] = 0
    return spectral_deriv
