import h5py
import librosa
import numpy as np
from django.test import TestCase
from scipy import signal

from koe.features.utils import my_stft
from pymlfunc import tictoc


class KoeUtilsTest(TestCase):
    def setUp(self):
        with h5py.File('tests/spectrogram1.h5', 'r') as hf:
            self.sig = hf['sig'].value.ravel()
            self.nfft = int(hf['nfft'].value[0][0])
            self.fs = int(hf['fs'].value[0][0])
            self.window_size = int(hf['window_size'].value[0][0])
            self.window = hf['window'].value.ravel()
            self.nfft = int(hf['nfft'].value[0][0])
            self.noverlap = int(hf['noverlap'].value[0][0])
            self.fs = int(hf['fs'].value[0][0])

            self.t = hf['t'].value.ravel()
            self.f = hf['f'].value.ravel()
            self.p = hf['p'].value.T

            s_imag = hf['is'].value.T
            s_real = hf['rs'].value.T
            self.s = s_real + 1j * s_imag

    def test_scipy_stft(self):
        with tictoc('test_scipy_stft'):
            f, t, s = signal.stft(self.sig, fs=self.fs, window=self.window, nperseg=self.window_size, padded=False,
                                  noverlap=self.noverlap, nfft=self.nfft, return_onesided=True, boundary=None)

            # Scipy's STFT is unscaled - where as Matlab's and librosa's are.
            s *= self.window.sum()

            self.assertTrue(np.allclose(f, self.f))
            self.assertTrue(np.allclose(t, self.t))
            self.assertTrue(np.allclose(s, self.s))

    def test_librosa_stft(self, ):
        with tictoc('test_librosa_stft'):
            hoplength = self.window_size - self.noverlap
            s = librosa.stft(y=self.sig, n_fft=self.nfft, win_length=self.window_size, hop_length=hoplength,
                             window=self.window, center=False)

            self.assertTrue(np.allclose(s, self.s))

    def test_my_stft(self, ):
        with tictoc('test_my_stft'):
            s = my_stft(sig=self.sig, fs=self.fs, nfft=self.nfft, window=self.window, noverlap=self.noverlap)

            self.assertTrue(np.allclose(s, self.s))
