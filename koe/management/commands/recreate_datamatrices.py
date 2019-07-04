"""
Remove all ghost spectrograms / masks
"""

from django.core.management.base import BaseCommand

from koe.feature_utils import extract_database_measurements
from koe.models import DataMatrix, Task


class Command(BaseCommand):

    def handle(self, *args, **options):
        dms = DataMatrix.objects.all()
        for dm in dms:
            if dm.database is None and dm.tmpdb is None:
                dm.delete()
                continue
            task = Task.objects.filter(target='{}:{}'.format(DataMatrix.__name__, dm.id)).first()
            if task is None:
                continue
            print('Extracting: Task# {}, DM#: '.format(task.id, dm.id))
            extract_database_measurements(task.id)
