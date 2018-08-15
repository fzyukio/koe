import os
import copy
import uuid

import numpy as np
from django.test import TestCase

import koe.binstorage as bs


def one_randint(limit=10):
    return np.random.randint(limit, size=1)[0]


def one_randbool():
    return one_randint(100) < 50


def create_random_id_based_dataset(npoints=10, max_len=100):
    """
    Create a set of random (unique) IDs and value arrays of various sizes, alternating between 1&2 dimensional
    :param max_len: max length of a value array
    :param npoints: number of IDs
    :return: ids (int32) and value arrays (float32)
    """
    ids = np.arange(npoints)
    np.random.shuffle(ids)

    arrs = []

    for i in range(npoints):
        arr_len = one_randint(max_len)
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
            self._test_retrieve()
        finally:
            os.remove(self.index_filename)
            os.remove(self.value_filename)

    def _test_store(self):
        bs.store(self.ids, self.arrs, self.index_filename, self.value_filename)
        with open(self.index_filename, 'rb') as f:
            index_arr = np.fromfile(f, dtype=np.int32)
            nids = len(index_arr) // bs.INDEX_FILE_NCOLS

            self.assertEqual(nids, len(self.ids))

            sort_order = np.argsort(self.ids)
            sorted_ids = self.ids[sort_order]
            sorted_arrs = [self.arrs[i] for i in sort_order]

            index_arr = index_arr.reshape((nids, bs.INDEX_FILE_NCOLS))
            for i in range(nids):
                id = sorted_ids[i]
                arr = sorted_arrs[i]

                arr_size = np.size(arr)
                id_, beg, end, dim0, dim1 = index_arr[i]

                self.assertEqual(id, id_)
                self.assertEqual(end - beg, arr_size)
                self.assertEqual(dim0, arr.shape[0])
                self.assertEqual(dim1, arr.shape[1] if arr.ndim == 2 else 0)
                self.assertEqual(dim0 * max(dim1, 1), arr_size)

        with open(self.value_filename, 'rb') as f:
            value_arr = np.fromfile(f, dtype=np.float32)
            self.assertEqual(len(value_arr), sum([np.size(arr) for arr in sorted_arrs]))

            arrs_ravel = np.concatenate([x.ravel() for x in sorted_arrs])
            self.assertTrue(np.allclose(value_arr, arrs_ravel))

    def _test_retrieve(self):
        selected_ids = copy.deepcopy(self.ids)
        np.random.shuffle(selected_ids)
        nselected = max(1, one_randint(len(self.ids)))
        selected_ids = selected_ids[:nselected]

        selected_ids_inds = [np.where(self.ids == x)[0][0] for x in selected_ids]
        selected_arrs = [self.arrs[i] for i in selected_ids_inds]
        retrieved_arrs = bs.retrieve(selected_ids, self.index_filename, self.value_filename)

        self.assertEqual(len(selected_ids), len(retrieved_arrs))
        for i in range(len(selected_ids)):
            selected_arr = selected_arrs[i]
            retrieved_arr = retrieved_arrs[i]

            self.assertTrue(np.allclose(selected_arr, retrieved_arr))
