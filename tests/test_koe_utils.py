import h5py
import numpy as np
from django.test import TestCase
from memoize import memoize
from scipy.stats import zscore

from koe import wavfile
from koe.utils import wav_2_mono
from koe.utils import split_segments, split_classwise, divide_conquer, one_hot, get_closest_neighbours


@memoize(timeout=60)
def _cached_foo(arg1, arg2, args):
    key = '{}-{}-{}'.format(arg1, arg2, '-'.join('{}={}'.format(x, y) for x, y in args.items()))
    if key in _cached_foo.cached:
        _cached_foo.cached[key] += 1
    else:
        _cached_foo.cached[key] = 1
    return '#{}:{}'.format(_cached_foo.cached[key], key)


_cached_foo.cached = {}


def one_randint(limit=10):
    return np.random.randint(limit, size=1)[0]


class KoeUtilsTest(TestCase):
    def test_segments_with_tail(self):
        nsegs, segs = split_segments(86, 32, 16, incltail=True)
        correct_segs = np.array([[0, 32], [16, 48], [32, 64], [48, 80], [64, 86]])
        correct_nsegs = len(correct_segs)

        self.assertEqual(nsegs, correct_nsegs)
        self.assertTrue((segs == correct_segs).all())

    def test_segments_without_tail(self):
        nsegs, segs = split_segments(86, 32, 16, incltail=False)
        correct_segs = np.array([[0, 32], [16, 48], [32, 64], [48, 80]])
        correct_nsegs = len(correct_segs)

        self.assertEqual(nsegs, correct_nsegs)
        self.assertTrue((segs == correct_segs).all())

    def test_read_segment(self):
        filepath = 'tests/example 1.wav'

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
        with h5py.File('tests/zscore.h5', 'r') as hf:
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

    def test_split_kfold_classwise(self):
        nclasses = 10
        k = 10
        max_ninstances = 100
        min_ninstances = k

        labels = []
        for i in range(nclasses):
            ninstances = min_ninstances + one_randint(max_ninstances - min_ninstances)
            labels += [i] * ninstances

        labels = np.array(labels, dtype=int)
        np.random.shuffle(labels)
        folds_iter1 = split_classwise(labels, k)
        folds_iter2 = split_classwise(labels, k)

        sorted_indices = np.arange(len(labels))
        self.assertEqual(len(folds_iter1), k)
        self.assertEqual(len(folds_iter2), k)

        for i in range(k):
            fold1 = folds_iter1[i]
            fold2 = folds_iter2[i]

            test1 = fold1['test']
            train1 = fold1['train']

            test2 = fold2['test']
            train2 = fold2['train']

            all1 = np.concatenate((test1, train1))
            all1.sort()

            all2 = np.concatenate((test2, train2))
            all2.sort()

            self.assertEqual(len(np.intersect1d(test1, train1)), 0)
            self.assertTrue(np.all(sorted_indices == all1))

            self.assertEqual(len(np.intersect1d(test2, train2)), 0)
            self.assertTrue(np.all(sorted_indices == all2))

            self.assertTrue(np.all(all1 == all2))
            self.assertFalse(len(test1) != len(test2) or np.all(test1 == test2))
            self.assertFalse(len(train1) != len(train2) or np.all(train1 == train2))

    def test_divide_conquer(self):
        n = 3

        # case 1: array's length is smaller than 10n
        arr_len = 2
        arr = np.arange(1, arr_len + 1)
        divs = divide_conquer(arr, n)

        divs_ = [np.array([1, 1]), np.array([1, 2]), np.array([2, 2])]

        for i in range(n):
            self.assertTrue(np.allclose(divs[i], divs_[i]))

        # case 1: array's length is larger than 10n
        arr_len = 32
        arr = np.arange(1, arr_len + 1)
        divs = divide_conquer(arr, n)

        divs_ = [np.arange(1, 12), np.arange(11, 23), np.arange(22, 33)]

        for i in range(n):
            self.assertTrue(np.allclose(divs[i], divs_[i]))

    def test_one_hot(self):
        labels = ['A', 'BC', 'D', 'BC']
        correct = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 1, 0]]

        encoded_labels, _ = one_hot(labels)
        self.assertTrue(np.allclose(correct, encoded_labels))

    def test_get_closest_neighbours(self):
        distmat = np.array([
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
        ]) / 10.

        labels = np.array(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])
        get_closest_neighbours(distmat, labels)
