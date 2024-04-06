from django.test import TestCase

import numpy as np
from dotmap import DotMap
from scipy.io import loadmat

from koe.features.time_domain import energy_envelope, log_attack_time, temporal_centroid
from koe.utils import wav_2_mono


nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap
tol = 1e-4


class Test(TestCase):
    def setUp(self):
        filepath = "tests/example 1.wav"
        self.fs, self.sig = wav_2_mono(filepath, normalised=True)
        self.sig = np.ascontiguousarray(self.sig)

        self.args = dict(
            nfft=nfft,
            noverlap=noverlap,
            win_length=win_length,
            fs=self.fs,
            wav_file_path=None,
            start=0,
            end=None,
            sig=self.sig,
            center=True,
        )

        saved = DotMap(loadmat("tests/time-domain.mat"))
        self.energy = saved.energy.ravel()
        self.lat = saved.lat.ravel()[0]
        self.tc = saved.tc.ravel()[0]

    def test_energy_envelope(self):
        envelope = energy_envelope(self.args)
        self.assertTrue(np.allclose(envelope, self.energy))

    def test_log_attack_time(self):
        lat = log_attack_time(self.args)
        self.assertAlmostEqual(lat, self.lat)

    def test_temporal_centroid(self):
        tc = temporal_centroid(self.args)
        self.assertAlmostEqual(tc, self.tc)
