import numpy as np
from django.test import TestCase
from dotmap import DotMap
from scipy.io import loadmat
from scipy.io import savemat

from koe.features.freq_domain import harmonic_ratio
from koe.utils import wav_2_mono


# nfft = 512
# noverlap = nfft * 3 // 4
# win_length = nfft
# stepsize = nfft - noverlap
# tol = 1e-4


class Test(TestCase):
    def setUp(self):
        filepath = 'tests/example 1.wav'
        self.fs, self.sig = wav_2_mono(filepath, normalised=True)
        self.sig = np.ascontiguousarray(self.sig)

        saved = DotMap(loadmat('tests/freq-domain.mat'))
        self.winlen = saved.winlen.ravel()[0]
        self.nfft = saved.nfft.ravel()[0]
        self.noverlap = saved.noverlap.ravel()[0]
        self.sdecrease = saved.sdecrease.ravel()
        self.window = saved.window.ravel()

        self.args = dict(nfft=self.nfft, noverlap=self.noverlap, window=self.window, win_length=self.winlen, fs=self.fs,
                         wav_file_path=None, start=0, end=None, sig=self.sig, center=False)

    # def test_spectral_flux(self):
    #     stepsize = self.nfft - self.noverlap
    #     psd, _ = _spectrogram(y=self.sig, S=None, n_fft=self.nfft, hop_length=stepsize)
    #     sf = spectral_flux(self.args)
    #
    # def test_spectral_decrease(self):
    #     sdecrease = spectral_decrease(self.args)
    #     self.assertTrue(np.allclose(sdecrease, self.sdecrease))

    def test_harmonic(self):
        hrs, f0s = harmonic_ratio(self.args)
        savemat('/tmp/freq-domain.mat', dict(hrs=hrs, f0s=f0s))
