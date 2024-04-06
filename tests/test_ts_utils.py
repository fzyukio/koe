import os
from uuid import uuid4

import django
from django.test import TestCase

import numpy as np
from pymlfunc import tictoc
from sklearn.decomposition import PCA as pca


class TsUtilsTest(TestCase):
    def test_bytes_to_ndarray(self):
        django.setup()
        from koe.ts_utils import bytes_to_ndarray, ndarray_to_bytes

        arr = np.random.rand(100, 200).astype(np.float32)
        filename = "/tmp/{}.bytes".format(uuid4().hex)

        ndarray_to_bytes(arr, filename)
        arr_ = bytes_to_ndarray(filename).reshape((100, 200))

        os.remove(filename)

        self.assertTrue(np.allclose(arr, arr_))

    def test_pca(self):
        django.setup()
        from koe.models import Aggregation, Database, Feature, FullTensorData
        from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary

        database = Database.objects.get(name="Bellbird_TMI")
        features = Feature.objects.all().order_by("id")
        aggregations = Aggregation.objects.all().order_by("id")
        features_hash = "-".join(list(map(str, features.values_list("id", flat=True))))
        aggregations_hash = "-".join(list(map(str, aggregations.values_list("id", flat=True))))

        full_tensor = FullTensorData.objects.filter(
            database=database,
            features_hash=features_hash,
            aggregations_hash=aggregations_hash,
        ).first()
        if full_tensor is None:
            raise Exception("Tensor not found")

        full_sids_path = full_tensor.get_sids_path()
        full_bytes_path = full_tensor.get_bytes_path()

        sids = bytes_to_ndarray(full_sids_path, np.int32)
        full_data = get_rawdata_from_binary(full_bytes_path, len(sids))

        with tictoc("PCA"):
            dim_reduce_func = pca(n_components=50)
            dim_reduce_func.fit_transform(full_data)
