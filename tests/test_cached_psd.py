import numpy as np

from django.test import TestCase
from librosa import feature as rosaft
from librosa.core.spectrum import _spectrogram

from koe.features.freq_domain import spectral_flatness, spectral_bandwidth, spectral_centroid, spectral_contrast,\
    spectral_rolloff
from koe.features.scaled_freq_features import mfcc
from koe.features.utils import get_psd, stft_from_sig
from koe.utils import wav_2_mono


nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap
tol = 1e-4


class Test(TestCase):
    def setUp(self):
        filepath = 'tests/example 1.wav'
        self.fs, self.sig = wav_2_mono(filepath, normalised=True)
        self.sig = np.ascontiguousarray(self.sig)

        self.args = dict(nfft=nfft, noverlap=noverlap, win_length=win_length, fs=self.fs, wav_file_path=None, start=0,
                         end=None, sig=self.sig, center=True)

    def test_stft_from_sig(self):
        psd1, _ = _spectrogram(y=self.sig, S=None, n_fft=nfft, hop_length=stepsize)
        psd2 = np.abs(stft_from_sig(self.sig, nfft, noverlap, win_length, 'hann', True))

        self.assertTrue(np.allclose(psd1, psd2))

    def test_get_psd(self):
        psd1, _ = _spectrogram(y=self.sig, S=None, n_fft=nfft, hop_length=stepsize)
        psd2 = get_psd(self.args)

        self.assertTrue(np.allclose(psd1, psd2))

    def test_spectral_flatness(self):
        correct = rosaft.spectral_flatness(y=self.sig, S=None, n_fft=nfft, hop_length=stepsize)
        actual = spectral_flatness(self.args)

        self.assertTrue(np.abs(correct - actual).max() < tol)

    def test_spectral_bandwidth(self):
        correct = rosaft.spectral_bandwidth(y=self.sig, sr=self.fs, S=None, n_fft=nfft, hop_length=stepsize)
        actual = spectral_bandwidth(self.args)

        self.assertTrue(np.abs(correct - actual).max() < tol)

    def test_spectral_centroid(self):
        correct = rosaft.spectral_centroid(y=self.sig, sr=self.fs, S=None, n_fft=nfft, hop_length=stepsize)
        actual = spectral_centroid(self.args)

        self.assertTrue(np.abs(correct - actual).max() < tol)

    def test_spectral_contrast(self):
        correct = rosaft.spectral_contrast(y=self.sig, sr=self.fs, S=None, n_fft=nfft, hop_length=stepsize)
        actual = spectral_contrast(self.args)

        self.assertTrue(np.abs(correct - actual).max() < tol)

    def test_spectral_rolloff(self):
        correct = rosaft.spectral_rolloff(y=self.sig, sr=self.fs, S=None, n_fft=nfft, hop_length=stepsize)
        actual = spectral_rolloff(self.args)

        self.assertTrue(np.abs(correct - actual).max() < tol)

    def test_mfcc(self):
        correct = rosaft.mfcc(y=self.sig, sr=self.fs, n_fft=nfft, hop_length=stepsize)
        actual = mfcc(self.args)

        self.assertTrue(np.abs(correct - actual).max() < tol)
