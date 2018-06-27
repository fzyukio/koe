import h5py
import numpy as np
from django.test import TestCase
from memoize import memoize
from scipy.stats import zscore

from koe import wavfile
from koe.management.commands.utils import wav_2_mono
from koe.utils import segments


@memoize(timeout=60)
def _cached_foo(arg1, arg2, args):
    key = '{}-{}-{}'.format(arg1, arg2, '-'.join('{}={}'.format(x, y) for x, y in args.items()))
    if key in _cached_foo.cached:
        _cached_foo.cached[key] += 1
    else:
        _cached_foo.cached[key] = 1
    return '#{}:{}'.format(_cached_foo.cached[key], key)


_cached_foo.cached = {}


class KoeUtilsTest(TestCase):
    def test_segments_with_tail(self):
        nsegs, segs = segments(86, 32, 16, incltail=True)
        correct_segs = np.array([[0, 32], [16, 48], [32, 64], [48, 80], [64, 86]])
        correct_nsegs = len(correct_segs)

        self.assertEqual(nsegs, correct_nsegs)
        self.assertTrue((segs == correct_segs).all())

    def test_segments_without_tail(self):
        nsegs, segs = segments(86, 32, 16, incltail=False)
        correct_segs = np.array([[0, 32], [16, 48], [32, 64], [48, 80]])
        correct_nsegs = len(correct_segs)

        self.assertEqual(nsegs, correct_nsegs)
        self.assertTrue((segs == correct_segs).all())

    def test_read_segment(self):
        filepath = 'example 1.wav'

        fs, sig = wav_2_mono(filepath, normalised=True)
        full_siglen = len(sig)

        # Test read_segment for the full duration (end_ms = None, beg_ms = 0)
        segment0 = wavfile.read_segment(filepath, mono=True)
        self.assertEqual(full_siglen, len(segment0))

        # Test reading segments of different length from different starting points.
        # The returned segment must have the prescribed length
        for beg_ms in [0, 1, 2, 20, 30, 100]:
            for length_ms in [100, 150, 153, 200]:
                end_ms = beg_ms + length_ms
                segment1 = wavfile.read_segment(filepath, beg_ms=beg_ms, end_ms=end_ms, mono=True)
                segment1_len_ms = np.round(len(segment1) * 1000 / fs)

                self.assertEqual(segment1_len_ms, length_ms)

    def test_zscore(self):
        with h5py.File('zscore.h5', 'r') as hf:
            x = hf['x'].value.ravel()
            self.z = hf['z'].value.ravel()
            xx = hf['xx'].value.T
            self.zz = hf['zz'].value.T

            z = zscore(x)
            self.assertTrue(np.allclose(z, self.z))

            zz = zscore(xx)
            self.assertTrue(np.allclose(zz, self.zz))

    def test_memorise(self):
        cached1 = _cached_foo(1, 2, dict(x=1, y=2))
        self.assertEqual('#1:1-2-x=1-y=2', cached1)

        cached2 = _cached_foo(2, 2, dict(x=1, y=2))
        cached2 = _cached_foo(2, 2, dict(x=1, y=2))
        cached2 = _cached_foo(2, 2, dict(x=1, y=2))
        cached2 = _cached_foo(2, 2, dict(x=1, y=2))
        self.assertEqual('#1:2-2-x=1-y=2', cached2)

        cached3 = _cached_foo(1, 2, dict(x=1, y=2))
        self.assertEqual('#1:1-2-x=1-y=2', cached3)

        cached4 = _cached_foo(2, 2, dict(x=1, y=2, z=1))
        self.assertEqual('#1:2-2-x=1-y=2-z=1', cached4)
