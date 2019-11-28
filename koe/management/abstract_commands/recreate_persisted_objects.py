import abc
import os

import numpy as np
from django.core.management import BaseCommand

from koe.models import Segment
from koe.ts_utils import bytes_to_ndarray

MISSING = 1
INCONSISTENT = 2
ALL_GOOD = 3


class RecreateIdsPersistentObjects(BaseCommand):
    @staticmethod
    def check_rebuild_necessary(obj, when):
        ord_sids_path = obj.get_sids_path()
        ord_bytes_path = obj.get_bytes_path()

        status = ALL_GOOD

        is_missing = not (os.path.isfile(ord_sids_path) and os.path.isfile(ord_bytes_path))

        if is_missing:
            status = MISSING
        else:
            sids = bytes_to_ndarray(ord_sids_path, np.int32)
            existing_count = Segment.objects.filter(id__in=sids).count()

            if len(sids) != existing_count:
                status = INCONSISTENT

        if when == 'missing':
            if status == MISSING:
                print('Re-constructing {} due to missing binary'.format(obj))
                return True
            else:
                print('Skip {} because it\'s binary files are not missing'.format(obj))
        elif when == 'inconsistent':
            if status == INCONSISTENT:
                print('Re-constructing {} due to binary being inconsistent with database'.format(obj))
                return True
            elif status == MISSING:
                print('Re-constructing {} due to missing binary'.format(obj))
                return True
            else:
                print('Skip {} because it\'s binary files are consistent with the database'.format(obj))
        else:
            print('Forced re-constructing {}'.format(obj))
            return True

        return False

    @abc.abstractmethod
    def perform_action(self, when, remove_dead):
        pass

    def add_arguments(self, parser):
        parser.add_argument('--when', action='store', dest='when', default='missing', type=str)
        parser.add_argument('--remove-dead', action='store_true', dest='remove_dead', default=False)

    def handle(self, *args, **options):
        when = options['when']
        remove_dead = options['remove_dead']

        when_values = ['missing', 'inconsistent', 'always']

        assert when in when_values, '--when can only be one of {}'.format(when_values)

        self.perform_action(when, remove_dead)
