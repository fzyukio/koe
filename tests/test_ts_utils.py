import os
from uuid import uuid4

import numpy as np
from django.test import TestCase

from koe.ts_utils import bytes_to_ndarray, ndarray_to_bytes


class TsUtilsTest(TestCase):
    def test_bytes_to_ndarray(self):
        arr = np.random.rand(100, 200).astype(np.float32)
        filename = '/tmp/{}.bytes'.format(uuid4().hex)

        ndarray_to_bytes(arr, filename)
        arr_ = bytes_to_ndarray(filename).reshape((100, 200))

        os.remove(filename)

        self.assertTrue(np.allclose(arr, arr_))
