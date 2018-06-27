import os
from uuid import uuid4

import h5py
import numpy as np
from django.test import TestCase
from librosa import stft
from scipy.io.wavfile import write

from koe.features.mt_features import mtspect, amplitude, entropy, mean_frequency, goodness_of_pitch, \
    frequency_modulation, amplitude_modulation, spectral_derivative, time_derivative, freq_derivative, find_zc, \
    frequency_contours, spectral_continuity
from spectrum import dpss
from tests.utils import tictoc


class KoeUtilsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        with h5py.File('mtspect.h5', 'r') as hf:
            cls.noverlap = int(hf['noverlap'].value[0][0])
            cls.nfft = int(hf['nfft'].value[0][0])
            cls.window_length = int(hf['window_length'].value[0][0])
            cls.tapers = hf['tapers'].value.T
            cls.sig = hf['sig'].value.ravel()
            cls.fm = hf['fm'].value.ravel()
            cls.am = hf['am'].value.ravel()

            cls.fs = int(hf['fs'].value[0][0])
            cls.s = hf['s'].value.T
            cls.goodness = hf['goodness'].value.T
            cls.amplitude = hf['amplitude'].value.T
            cls.entropy = hf['entropy'].value.T
            cls.mean_frequency = hf['mean_frequency'].value.T

            cls.time_deriv = hf['time_deriv'].value.T
            cls.freq_deriv = hf['freq_deriv'].value.T
            cls.derivs = hf['derivs'].value.T
            cls.contours = hf['contours'].value.T.astype(np.bool)
            cls.continuity = hf['continuity_frame'].value.T

            cls.peaks_x = (hf['peaks_x'].value.ravel().astype(np.int64) - 1)
            cls.peaks_y = (hf['peaks_y'].value.ravel().astype(np.int64) - 1)

            cls.peaks_x.sort()
            cls.peaks_y.sort()

            cls.wav_file_path = '/tmp/{}.wav'.format(uuid4().hex)
            data = cls.sig.astype(np.float32)

            normfactor = 1.0 / (2 ** (16 - 1))
            data /= normfactor
            data = data.astype(np.int16)

            write(cls.wav_file_path, cls.fs, data)
            cls.args = dict(wav_file_path=cls.wav_file_path, start=0, end=None, nfft=cls.nfft,
                            win_length=cls.window_length, noverlap=cls.noverlap, fs=cls.fs)

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.wav_file_path)

    def test_circshift(self):
        x = np.array([[1, 2, 3], [5, 6, 7], [2, 3, 4]])
        x_ = np.array([[5, 6, 7], [2, 3, 4], [1, 2, 3]])
        y = np.roll(x, -1, 0)
        self.assertTrue((x_ == y).all())

    def test_find_zc(self):
        x = np.array(
            [-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, 0.00011864,
             -0.00010467, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, 0.001871,
             0.014847, -0.016339, 0.0004225, -0.00034053, -5.5669e-05, -0.1, -0.1])

        v_ = x * np.roll(x, 1, 0)
        idx = np.where((v_ < 0) & (x < 0))[0]

        self.assertTrue(np.array_equal(idx, [17, 33, 35]))

    def test_dpss(self):
        cls = self.__class__
        tapers, eigen = dpss(cls.nfft, 1.5, 2)
        self.assertTrue(np.allclose(tapers, cls.tapers))

    def test_mt_spect(self):
        cls = self.__class__
        s = mtspect(cls.args)
        self.assertTrue(np.allclose(s, cls.s))

    def test_mean_frequency(self):
        cls = self.__class__
        mf = mean_frequency(cls.args)
        self.assertTrue(np.allclose(mf, cls.mean_frequency))

    def test_amplitude(self):
        cls = self.__class__
        a = amplitude(cls.args)
        self.assertTrue(np.allclose(a, cls.amplitude))

    def test_entropy(self):
        cls = self.__class__
        e = entropy(cls.args)
        self.assertTrue(np.allclose(e, cls.entropy))

    def test_goodness_of_pitch(self):
        cls = self.__class__
        gop = goodness_of_pitch(cls.args)
        self.assertTrue(np.allclose(gop, cls.goodness))

    def test_frequency_modulation(self):
        cls = self.__class__
        fm = frequency_modulation(cls.args)
        self.assertTrue(np.allclose(fm, cls.fm))

    def test_amplitude_modulation(self):
        cls = self.__class__
        am = amplitude_modulation(cls.args)
        self.assertTrue(np.allclose(am, cls.am))

    def test_spectral_derivative(self):
        cls = self.__class__
        derivs = spectral_derivative(cls.args)
        self.assertTrue(np.allclose(derivs, cls.derivs))

    def test_time_derivative(self):
        cls = self.__class__
        td = time_derivative(cls.args)
        self.assertTrue(np.allclose(td, cls.time_deriv))

    def test_freq_derivative(self):
        cls = self.__class__
        fd = freq_derivative(cls.args)
        self.assertTrue(np.allclose(fd, cls.freq_deriv))

    def test_frequency_contours(self):
        cls = self.__class__
        contours = frequency_contours(cls.args)
        self.assertTrue(np.allclose(contours, cls.contours))

    def test_spectral_continuity(self):
        cls = self.__class__
        continuity = spectral_continuity(cls.args)
        self.assertTrue(np.allclose(continuity, cls.continuity))

    def test_spectral_derivatives(self):
        cls = self.__class__
        with tictoc('test_spectral_derivatives'):
            hopsize = cls.window_length - cls.noverlap
            taper1 = cls.tapers[:, 0]
            taper2 = cls.tapers[:, 1]

            tapered1 = stft(y=cls.sig, n_fft=cls.nfft, win_length=cls.window_length, hop_length=hopsize,
                            window=taper1, center=False, dtype=np.complex128)
            tapered2 = stft(y=cls.sig, n_fft=cls.nfft, win_length=cls.window_length, hop_length=hopsize,
                            window=taper2, center=False, dtype=np.complex128)

            real1 = np.real(tapered1)
            real2 = np.real(tapered2)
            imag1 = np.imag(tapered1)
            imag2 = np.imag(tapered2)

            time_deriv = (-real1 * real2) - (imag1 * imag2)
            freq_deriv = (imag1 * real2) - (real1 * imag2)

            pfm = np.max(time_deriv, axis=0) / (np.max(freq_deriv, axis=0) + 0.1)
            fm = np.arctan(pfm)
            cfm = np.cos(fm)
            sfm = np.sin(fm)
            derivs = (time_deriv * sfm + freq_deriv * cfm)
            derivs[0:3, :] = 0

            self.assertTrue(np.allclose(time_deriv, cls.time_deriv))
            self.assertTrue(np.allclose(freq_deriv, cls.freq_deriv))
            self.assertTrue(np.allclose(derivs, cls.derivs))

            derivs_abs = np.abs(derivs)

            row_thresh = 0.3 * np.mean(derivs_abs, axis=0)
            col_thresh = 100 * np.median(derivs_abs, axis=1)

            mask_row = derivs_abs <= row_thresh[None, :]
            mask_col = derivs_abs <= col_thresh[:, None]
            mask = (mask_row | mask_col)
            derivs[mask] = -0.1

            zcy, zcx = find_zc(derivs)
            zcx.sort()
            zcy.sort()

            self.assertTrue(np.allclose(zcx, cls.peaks_x))
            self.assertTrue(np.allclose(zcy, cls.peaks_y))
