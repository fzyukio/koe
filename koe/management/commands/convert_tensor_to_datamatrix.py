import numpy as np
from django.core.management.base import BaseCommand

from koe.models import DataMatrix, DerivedTensorData, FullTensorData, Ordination
from koe.ts_utils import bytes_to_ndarray
from koe.ts_utils import get_rawdata_from_binary


class Command(BaseCommand):
    def handle(self, *args, **options):

        tensor_to_dm = {}
        DataMatrix.objects.all().delete()
        for tensor in FullTensorData.objects.all():
            sids_path = tensor.get_sids_path()
            bytes_path = tensor.get_bytes_path()

            sids = bytes_to_ndarray(sids_path, np.int32)
            data = get_rawdata_from_binary(bytes_path, len(sids))

            dm = DataMatrix.objects.filter(name=tensor.name).first()
            if dm is None:
                dm = DataMatrix.objects.create(
                    database=tensor.database,
                    name=tensor.name,
                    created=tensor.created,
                    features_hash=tensor.features_hash,
                    aggregations_hash=tensor.aggregations_hash,
                    ndims=data.shape[1]
                )

            tensor_to_dm[tensor] = dm

        Ordination.objects.filter(dm__in=tensor_to_dm.values()).delete()
        for tensor in DerivedTensorData.objects.exclude(dimreduce='none'):
            dm = tensor_to_dm[tensor.full_tensor]

            method = tensor.dimreduce
            ndims = tensor.ndims
            if method.startswith('tsne'):
                ndims = int(method[4:])
                method = 'tsne'

            Ordination.objects.create(dm=dm, method=method, ndims=ndims)
