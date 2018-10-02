import os
import shutil

import numpy as np
from django.core.management.base import BaseCommand

from koe.models import DataMatrix, DerivedTensorData, FullTensorData, Ordination
from koe.ts_utils import bytes_to_ndarray
from koe.ts_utils import get_rawdata_from_binary
from root.utils import ensure_parent_folder_exists


class Command(BaseCommand):
    def handle(self, *args, **options):

        tensor_to_dm = {}
        for tensor in FullTensorData.objects.all():
            sids_path = tensor.get_sids_path()
            bytes_path = tensor.get_bytes_path()
            cols_path = tensor.get_cols_path()

            sids = bytes_to_ndarray(sids_path, np.int32)
            data = get_rawdata_from_binary(bytes_path, len(sids))

            dm = DataMatrix.objects.filter(name=tensor.name).first()
            if dm is None:
                dm = DataMatrix.objects.create(
                    database=tensor.database,
                    name=tensor.name,
                    features_hash=tensor.features_hash,
                    aggregations_hash=tensor.aggregations_hash,
                    ndims=data.shape[1]
                )

            dm_sids_path = dm.get_sids_path()
            dm_bytes_path = dm.get_bytes_path()
            dm_cols_path = dm.get_cols_path()

            ensure_parent_folder_exists(dm_sids_path)

            shutil.copy(sids_path, dm_sids_path)
            shutil.copy(bytes_path, dm_bytes_path)
            shutil.copy(cols_path, dm_cols_path)

            tensor_to_dm[tensor] = dm

        for tensor in DerivedTensorData.objects.exclude(dimreduce='none'):
            dm = tensor_to_dm[tensor.full_tensor]
            sids_path = tensor.full_tensor.get_sids_path()
            bytes_path = tensor.get_bytes_path()

            if not os.path.exists(bytes_path):
                bytes_path = tensor.full_tensor.get_bytes_path()

            method = tensor.dimreduce
            ndims = tensor.ndims
            if method.startswith('tsne'):
                ndims = int(method[4:])
                method = 'tsne'

            ord = Ordination.objects.filter(dm=dm, method=method, ndims=ndims).first()
            if ord is None:
                ord = Ordination.objects.create(dm=dm, method=method, ndims=ndims)

            ord_sids_path = ord.get_sids_path()
            ord_bytes_path = ord.get_bytes_path()

            ensure_parent_folder_exists(ord_sids_path)

            shutil.copy(sids_path, ord_sids_path)
            shutil.copy(bytes_path, ord_bytes_path)
