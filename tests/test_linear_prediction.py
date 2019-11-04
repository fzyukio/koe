import numpy as np
from django.test import TestCase
from dotmap import DotMap
from numpy.testing import assert_allclose
from scipy.io import loadmat

from koe.features.linear_prediction import lpc_cepstrum, lpc_spectrum, lp_coefficients
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

        saved = DotMap(loadmat('tests/lpc.mat'))
        self.lpc_spect = saved.lpc_spect
        self.lpc_cepst = saved.lpc_cepst
        self.lp_coeffs = saved.lp_coeffs
        self.winlen = saved.winlen.ravel()[0]
        self.nfft = saved.nfft.ravel()[0]
        self.order = saved.order.ravel()[0]
        self.noverlap = saved.noverlap.ravel()[0]
        self.window = saved.window.ravel()

        self.args = dict(nfft=self.nfft, noverlap=self.noverlap, window=self.window, win_length=self.winlen, fs=self.fs,
                         wav_file_path=None, start=0, end=None, sig=self.sig, center=False, order=self.order)

    def test_lp_coefficients(self):
        lp_coeffs = lp_coefficients(self.args)
        assert_allclose(lp_coeffs, self.lp_coeffs, atol=1e-5)

    def test_lpc_spectrum(self):
        lpc_spect = lpc_spectrum(self.args)
        assert_allclose(lpc_spect, self.lpc_spect, atol=1e-5)

    def test_lpc_cepstrum(self):
        lpc_cepst = lpc_cepstrum(self.args)
        assert_allclose(lpc_cepst, self.lpc_cepst, atol=1e-5)
