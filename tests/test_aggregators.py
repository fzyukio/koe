import numpy as np
from django.test import TestCase
from librosa import feature as rosaft

from koe import wavfile

import django

from koe.management.utils.luscinia_utils import wav_2_mono

django.setup()

nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap
tol = 1e-4


class Test(TestCase):
    def setUp(self):
        filepath = 'tests/example 1.wav'
        self.fs, _ = wav_2_mono(filepath, normalised=False)
        long_segment = wavfile.read_segment(filepath, beg_ms=100, end_ms=300, mono=True)
        self.long_segment = np.ascontiguousarray(long_segment)

        short_segment = wavfile.read_segment(filepath, beg_ms=100, end_ms=149, mono=True)
        self.short_segment = np.ascontiguousarray(short_segment)

    def test_divcon_long(self):
        from koe.aggregator import DivideConquer
        ndivs = 5
        method = np.mean
        arr = rosaft.mfcc(y=self.long_segment, sr=self.fs, n_fft=nfft, hop_length=stepsize)

        aggregator = DivideConquer(method, ndivs)
        results = aggregator.process(arr)

        div_len = arr.shape[-1] / ndivs
        divs = []
        for i in range(ndivs):
            start = int(np.floor(i * div_len))
            end = int(np.ceil((i + 1) * div_len))
            div = arr[:, start:end]
            divs.append(div)

        correct = np.array([method(div, axis=-1) for div in divs]).ravel()
        self.assertTrue(np.allclose(correct, results))
