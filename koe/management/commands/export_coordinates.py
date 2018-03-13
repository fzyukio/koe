from django.core.management.base import BaseCommand
from koe.models import *
from scipy.io import savemat


class Command(BaseCommand):

    def handle(self, *args, **options):
        cs = Coordinate.objects.all()
        export = dict(count=len(cs))

        for idx, c in enumerate(cs):
            export['c_{}'.format(idx + 1)] = dict(c=c.coordinates, name=c.algorithm)

        savemat('/tmp/cs.mat', export)
