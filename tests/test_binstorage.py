import os
import copy
import uuid

import numpy as np
from django.test import TestCase
from pymlfunc import tictoc

import koe.binstorage as bs

NUM_POINTS = 100


def one_randint(max=100, min=1):
    return min + np.random.randint((max - min), size=1)[0]


def one_randbool():
    return one_randint(100) < 50


def create_random_id_based_dataset(npoints=NUM_POINTS, max_len=100):
    """
    Create a set of random (unique) IDs and value arrays of various sizes, alternating between 1&2 dimensional
    :param max_len: max length of a value array
    :param npoints: number of IDs
    :return: ids (int32) and value arrays (float32)
    """
    ids = np.arange(npoints * 10)
    np.random.shuffle(ids)
    ids = ids[:npoints]

    arrs = []

    for i in range(npoints):
        arr_len = one_randint(max_len)
        is_scalar = one_randbool()
        if is_scalar:
            arr = np.random.randn(1)[0]
        else:
            is_two_dims = one_randbool()
            if is_two_dims:
                arr_len2 = one_randint(max_len)
                arr = np.random.randn(arr_len, arr_len2)
            else:
                arr = np.random.randn(arr_len)
        arrs.append(arr)

    return ids, arrs


class BinStorageTest(TestCase):
    def setUp(self):
        self.ids, self.arrs = create_random_id_based_dataset()
        path = '/tmp'
        name = uuid.uuid4().hex
        self.index_filename = os.path.join(path, '{}.idx'.format(name))
        self.value_filename = os.path.join(path, '{}.val'.format(name))

    def test(self):
        try:
            self._test_store()

            for nselected in np.logspace(np.log10(10), np.log10(len(self.ids)), 10, dtype=np.int32):
                self._test_retrieve(nselected)

            for nupdate in np.logspace(np.log10(10), np.log10(len(self.ids)), 10, dtype=np.int32):
                self._test_update(nupdate)

            self._test_retrieve_error()

        finally:
            os.remove(self.index_filename)
            os.remove(self.value_filename)

    def _test_store(self):
        with tictoc('Test storing'):
            bs.store(self.ids, self.arrs, self.index_filename, self.value_filename)
        index_filesize = os.path.getsize(self.index_filename)
        index_memory_usage = len(self.ids) * bs.INDEX_FILE_NCOLS * 4

        value_filesize = os.path.getsize(self.value_filename)
        value_memory_usage = sum([np.size(x) for x in self.arrs]) * 4

        self.assertEqual(index_filesize, index_memory_usage)
        self.assertEqual(value_filesize, value_memory_usage)

        with open(self.index_filename, 'rb') as f:
            index_arr = np.fromfile(f, dtype=np.int32)
            nids = len(index_arr) // bs.INDEX_FILE_NCOLS

            self.assertEqual(nids, len(self.ids))

            index_arr = index_arr.reshape((nids, bs.INDEX_FILE_NCOLS))
            for i in range(nids):
                id = self.ids[i]
                arr = self.arrs[i]

                arr_size = np.size(arr)
                id_, beg, end, dim0, dim1 = index_arr[i]

                self.assertEqual(id, id_)
                self.assertEqual(end - beg, arr_size)
                self.assertEqual(dim0, arr.shape[0] if arr.ndim >= 1 else 0)
                self.assertEqual(dim1, arr.shape[1] if arr.ndim == 2 else 0)
                self.assertEqual(max(1, dim0) * max(dim1, 1), arr_size)

        with open(self.value_filename, 'rb') as f:
            value_arr = np.fromfile(f, dtype=np.float32)
            self.assertEqual(len(value_arr), sum([np.size(arr) for arr in self.arrs]))

            arrs_ravel = np.concatenate([x.ravel() for x in self.arrs])
            self.assertTrue(np.allclose(value_arr, arrs_ravel))

    def _test_update(self, nupdate):
        _, new_arrs = create_random_id_based_dataset()
        npoints = NUM_POINTS

        id2arr = {x: y for x, y in zip(self.ids, self.arrs)}

        # We want to make sure there are new ids (to be appended) and old ids (to be updated)
        while True:
            new_ids = np.arange(npoints * 10)
            np.random.shuffle(new_ids)
            new_ids = new_ids[:nupdate]
            nnew = np.array([x for x in new_ids if x not in self.ids])
            if 0 < len(nnew) < npoints:
                break

        for x, y in zip(new_ids, new_arrs):
            id2arr[x] = y

        self.ids = np.array(list(id2arr.keys()))
        np.random.shuffle(self.ids)

        self.arrs = [id2arr[i] for i in self.ids]

        with tictoc('Test update {} items'.format(nupdate)):
            bs.store(new_ids, new_arrs, self.index_filename, self.value_filename)

        retrieved_arrs = bs.retrieve(self.ids, self.index_filename, self.value_filename)
        for id, retrieved_arr in zip(self.ids, retrieved_arrs):
            self.assertTrue(np.allclose(id2arr[id], retrieved_arr))

    def _test_retrieve(self, nselected):
        selected_ids = copy.deepcopy(self.ids)
        np.random.shuffle(selected_ids)
        selected_ids = selected_ids[:nselected]

        selected_ids_inds = [np.where(self.ids == x)[0][0] for x in selected_ids]
        selected_arrs = [self.arrs[i] for i in selected_ids_inds]

        with tictoc('Test retrieving {} items'.format(nselected)):
            retrieved_arrs = bs.retrieve(selected_ids, self.index_filename, self.value_filename)

        self.assertEqual(len(selected_ids), len(retrieved_arrs))
        for i in range(len(selected_ids)):
            selected_arr = selected_arrs[i]
            retrieved_arr = retrieved_arrs[i]

            self.assertTrue(np.allclose(selected_arr, retrieved_arr))

    def _test_retrieve_error(self):
        non_existing_ids = NUM_POINTS * 10 + np.random.randint(100, size=5)

        with self.assertRaises(ValueError):
            bs.retrieve(non_existing_ids, self.index_filename, self.value_filename)
