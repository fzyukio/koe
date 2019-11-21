import copy
import os
import shutil
import uuid

import numpy as np
from django.test import TestCase
from pymlfunc import tictoc

import binstorage2 as bs

NUM_POINTS = 1000


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
        ids_sorted_order = np.argsort(self.ids)
        self.sorted_ids = np.array(self.ids)[ids_sorted_order]
        self.sorted_arrs = np.array(self.arrs)[ids_sorted_order]

        path = '/tmp'
        name = uuid.uuid4().hex
        self.loc = os.path.join(path, name)
        self.index_file = os.path.join(self.loc, '.index')
        os.mkdir(self.loc)

    def test(self):
        try:
            self._test_store()

            nselecteds = np.logspace(np.log10(NUM_POINTS // 1000), np.log10(len(self.ids) // 5), 10, dtype=np.int32)
            nupdates = np.logspace(np.log10(NUM_POINTS // 1000), np.log10(len(self.ids) // 5), 10, dtype=np.int32)

            for nselected in nselecteds:
                self._test_retrieve(nselected)

            for nupdate in nupdates:
                self._test_update(nupdate)

            self._test_retrieve_error()

        finally:
            shutil.rmtree(self.loc)

    def _test_store(self):
        with tictoc('Test storing'):
            bs.store(self.ids, self.arrs, self.loc)

        with open(self.index_file, 'rb') as f:
            index_arr = np.fromfile(f, dtype=np.int32)
            nids = len(index_arr) // bs.INDEX_FILE_NCOLS

            self.assertEqual(nids, len(self.ids))

            index_arr = index_arr.reshape((nids, bs.INDEX_FILE_NCOLS))
            val_file_template = os.path.join(self.loc, '{}.val')

            for i in range(nids):
                id = self.sorted_ids[i]
                arr = self.sorted_arrs[i]

                val_file = val_file_template.format(id)

                arr_size = np.size(arr)
                id_, dim0, dim1 = index_arr[i]

                self.assertEqual(id, id_)
                self.assertEqual(dim0, arr.shape[0] if arr.ndim >= 1 else 0)
                self.assertEqual(dim1, arr.shape[1] if arr.ndim == 2 else 0)
                self.assertEqual(max(1, dim0) * max(dim1, 1), arr_size)

                with open(val_file, 'rb') as f:
                    value_arr = np.fromfile(f, dtype=np.float32)
                    if dim1 == 0:
                        if dim0 == 0:
                            value_arr = value_arr[0]
                        else:
                            self.assertEqual(len(value_arr), dim0)
                    else:
                        self.assertEqual(len(value_arr), dim0 * dim1)
                        value_arr = value_arr.reshape((dim0, dim1))

                    self.assertTrue(np.allclose(value_arr, arr))

    def _test_update(self, nupdate):
        _, arrs_for_update = create_random_id_based_dataset(nupdate)

        id2arr = {x: y for x, y in zip(self.ids, self.arrs)}

        # We want to make sure there are new ids (to be appended) and old ids (to be updated)
        nkeeps = nupdate // 2
        nnews = nupdate - nkeeps

        maxid = np.max(self.ids)
        new_ids = np.arange(maxid + 1, maxid + nnews + 1)
        keep_ids = self.ids[:nkeeps]

        ids_for_update = np.concatenate((keep_ids, new_ids))

        for x, y in zip(ids_for_update, arrs_for_update):
            id2arr[x] = y

        self.ids = np.array(list(id2arr.keys()))
        np.random.shuffle(self.ids)

        self.arrs = [id2arr[i] for i in self.ids]

        with tictoc('Test update {} items'.format(nupdate)):
            bs.store(ids_for_update, arrs_for_update, self.loc)

        retrieved_arrs = bs.retrieve(self.ids, self.loc)
        for id, retrieved_arr in zip(self.ids, retrieved_arrs):
            self.assertTrue(np.allclose(id2arr[id], retrieved_arr))

    def _test_retrieve(self, nselected):
        selected_ids = copy.deepcopy(self.ids)
        np.random.shuffle(selected_ids)
        selected_ids = selected_ids[:nselected]

        selected_ids_inds = [np.where(self.ids == x)[0][0] for x in selected_ids]
        selected_arrs = [self.arrs[i] for i in selected_ids_inds]

        with tictoc('Test retrieving {} items'.format(nselected)):
            retrieved_arrs = bs.retrieve(selected_ids, self.loc)

        self.assertEqual(len(selected_ids), len(retrieved_arrs))
        for i in range(len(selected_ids)):
            selected_arr = selected_arrs[i]
            retrieved_arr = retrieved_arrs[i]

            self.assertTrue(np.allclose(selected_arr, retrieved_arr))

    def _test_retrieve_error(self):
        non_existing_ids = NUM_POINTS * 100 + np.random.randint(100, size=NUM_POINTS // 2)

        with self.assertRaises(ValueError):
            bs.retrieve(non_existing_ids, self.loc)
