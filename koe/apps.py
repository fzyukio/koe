import numpy as np

from django.apps import AppConfig


class KoeConfig(AppConfig):
    name = 'koe'

    def ready(self):
        from root.views import register_view
        register_view(self.name, 'views')
        # from koe.models import DistanceMatrix
        # # DistanceMatrix.objects.all().delete()
        # dm = DistanceMatrix.objects.last()
        # if dm is None:
        #     dm = DistanceMatrix()
        #
        # # print(dm.triu)
        # # print(dm.element_ids)
        #
        # dm.triu = np.random.randint(np.iinfo(np.int32).max, size=(4, 4), dtype=np.int32)
        # dm.element_ids = np.random.randint(np.iinfo(np.int32).max, size=(4, ), dtype=np.int32)
        #
        # print(dm.triu)
        # print(dm.element_ids)
        #
        # dm.algorithm = 'test'
        # dm.save()