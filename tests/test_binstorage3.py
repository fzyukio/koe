import copy
import os
import shutil
import uuid

from django.test import TestCase

import numpy as np
from pymlfunc import tictoc

import koe.binstorage3 as bs


NUM_POINTS = 10000


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
    ids = np.arange(1, npoints * 10 + 1)
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

        path = "/tmp"
        name = uuid.uuid4().hex
        self.loc = os.path.join(path, name)
        self.index_file = os.path.join(self.loc, bs.INDEX_PREFIX)
        os.mkdir(self.loc)

    def test(self):
        try:
            self._test_store()

            nselecteds = np.logspace(
                np.log10(NUM_POINTS // 1000),
                np.log10(len(self.ids) // 5),
                10,
                dtype=np.int32,
            )
            nupdates = np.logspace(
                np.log10(NUM_POINTS // 1000),
                np.log10(len(self.ids) // 5),
                10,
                dtype=np.int32,
            )

            for nselected in nselecteds:
                self._test_retrieve(nselected)
                self._test_retrieve(nselected, False)

                self._test_retrieve_ids()
                min = one_randint(max=NUM_POINTS - nselected)
                self._test_retrieve_ids(limit=(min, min + nselected))

            for nupdate in nupdates:
                self._test_update(nupdate)

            self._test_retrieve_error()

        finally:
            shutil.rmtree(self.loc)

    def _test_store(self):
        with tictoc("Test storing"):
            bs.store(self.ids, self.arrs, self.loc)

        index_arr = []
        value_arr = []

        index_files = [x for x in os.listdir(self.loc) if x.startswith(bs.INDEX_PREFIX)]
        batches = {}
        for index_file in index_files:
            batch_begin, batch_end = list(map(int, index_file[len(bs.INDEX_PREFIX) :].split("-")))
            batches[batch_begin] = (batch_begin, batch_end, index_file)

        batch_begins = sorted(list(batches.keys()))
        for batch_begin in batch_begins:
            batch_begin, batch_end, index_file = batches[batch_begin]

            batch_part = index_file[len(bs.INDEX_PREFIX) :]
            index_file_path = os.path.join(self.loc, index_file)
            value_file_path = os.path.join(self.loc, bs.VALUE_PREFIX + batch_part)

            index_arr_ = np.fromfile(index_file_path, dtype=np.int32).reshape((-1, bs.INDEX_FILE_NCOLS))
            assert len(index_arr_) <= bs.BATCH_SIZE
            value_arr_ = np.fromfile(value_file_path, dtype=np.float32)

            index_arr.append(index_arr_)
            value_arr.append(value_arr_)

        index_arr = np.concatenate(index_arr).reshape((-1, bs.INDEX_FILE_NCOLS))
        value_arr = np.concatenate(value_arr)

        nids = len(index_arr)
        self.assertEqual(nids, len(self.ids))
        self.assertTrue(np.allclose(self.sorted_ids, index_arr[:, 0]))
        arrs_ravel = np.concatenate([x.ravel() for x in self.sorted_arrs])
        self.assertTrue(np.allclose(value_arr, arrs_ravel))

        for id, arr, stored_index in zip(self.sorted_ids, self.sorted_arrs, index_arr):
            stored_id, _, _, stored_dim0, stored_dim1 = stored_index

            arr_size = np.size(arr)
            self.assertEqual(id, stored_id)
            self.assertEqual(stored_dim0, arr.shape[0] if arr.ndim >= 1 else 0)
            self.assertEqual(stored_dim1, arr.shape[1] if arr.ndim == 2 else 0)
            self.assertEqual(max(1, stored_dim0) * max(stored_dim1, 1), arr_size)

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

        with tictoc("Test update {} items".format(nupdate)):
            bs.store(ids_for_update, arrs_for_update, self.loc)

        retrieved_arrs = bs.retrieve(self.ids, self.loc)
        for id, retrieved_arr in zip(self.ids, retrieved_arrs):
            self.assertTrue(np.allclose(id2arr[id], retrieved_arr))

    def _test_retrieve(self, nselected, shuffle=True):
        selected_ids = copy.deepcopy(self.ids)
        if shuffle:
            np.random.shuffle(selected_ids)
        selected_ids = selected_ids[:nselected]

        selected_ids_inds = [np.where(self.ids == x)[0][0] for x in selected_ids]
        selected_arrs = [self.arrs[i] for i in selected_ids_inds]

        with tictoc("Test retrieving {} items shuffle={}".format(nselected, shuffle)):
            retrieved_arrs = bs.retrieve(selected_ids, self.loc)

        self.assertEqual(len(selected_ids), len(retrieved_arrs))
        for i in range(len(selected_ids)):
            selected_arr = selected_arrs[i]
            retrieved_arr = retrieved_arrs[i]

            try:
                self.assertTrue(np.allclose(selected_arr, retrieved_arr))
            except TypeError:
                pass

    def _test_retrieve_ids(self, limit=None):
        with tictoc("Test retrieving IDs limit={}".format(limit)):
            ids = bs.retrieve_ids(self.loc, limit)

        if limit:
            min, max = limit
            self.assertGreaterEqual(ids.min(), min - bs.BATCH_SIZE)
            self.assertLessEqual(ids.max(), max + bs.BATCH_SIZE)

    def _test_retrieve_error(self):
        non_existing_ids = NUM_POINTS * 100 + np.random.randint(100, size=NUM_POINTS // 2)

        with self.assertRaises((ValueError, FileNotFoundError)):
            bs.retrieve(non_existing_ids, self.loc)
