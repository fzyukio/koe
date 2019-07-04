import numpy as np
from django.test import TestCase

from koe.features.scaled_freq_features import mfcc_delta2
from koe.management.utils.luscinia_utils import wav_2_mono

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

    def test_mfcc_delta(self):
        mfcc_delta2(self.args)
