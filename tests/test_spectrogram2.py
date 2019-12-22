import json

import librosa
import numpy as np
from django.test import TestCase
from scipy import signal

from koe.features.utils import my_stft, _cached_get_window
from pymlfunc import tictoc


class KoeUtilsTest(TestCase):
    def setUp(self):
        with open('tests/spectrogram.json', 'r') as f:
            data = json.loads(f.read())

        s_real = np.array(data['rs'])
        s_imag = np.array(data['is'])
        self.s = s_real + 1j * s_imag

        self.nfft = data['nfft']
        self.window = np.array(data['hanning'])
        self.window_size = data['window']
        self.sig = np.array(data['sig'])
        self.fs = data['fs']
        self.nfft = data['nfft']
        self.noverlap = data['noverlap']

    def test_window(self):
        with tictoc('test_window'):
            correct_window = [0.5 * (1 - np.cos(2 * np.pi * n / (self.nfft - 1))) for n in range(self.nfft)]
            window = _cached_get_window('hann', self.nfft)

            self.assertTrue(np.allclose(window, self.window))
            self.assertTrue(np.allclose(window, correct_window))

    def test_scipy_stft(self):
        with tictoc('test_scipy_stft'):
            f, t, s = signal.stft(self.sig, fs=self.fs, window=self.window, nperseg=self.window_size, padded=False,
                                  noverlap=self.noverlap, nfft=self.nfft, return_onesided=True, boundary=None)

            # Scipy's STFT is unscaled - where as Matlab's and librosa's are.
            s *= self.window.sum()
            self.assertTrue(np.allclose(s.T, self.s))

    def test_librosa_stft(self, ):
        with tictoc('test_librosa_stft'):
            hoplength = self.window_size - self.noverlap
            s = librosa.stft(y=self.sig, n_fft=self.nfft, win_length=self.window_size, hop_length=hoplength,
                             window=self.window, center=False)

            self.assertTrue(np.allclose(s.T, self.s))

    def test_my_stft(self, ):
        with tictoc('test_my_stft'):
            s = my_stft(sig=self.sig, fs=self.fs, nfft=self.nfft, window=self.window, noverlap=self.noverlap)

            self.assertTrue(np.allclose(s.T, self.s))
