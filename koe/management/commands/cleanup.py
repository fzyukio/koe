"""
Remove all ghost spectrograms / masks
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from koe.models import Segment


class Command(BaseCommand):

    def handle(self, *args, **options):
        spect_dir = os.path.join(settings.MEDIA_URL, 'spect', 'fft', 'syllable')[1:]
        mask_dir = os.path.join(settings.MEDIA_URL, 'spect', 'mask')[1:]

        spect_files = os.listdir(spect_dir)
        mask_files = os.listdir(mask_dir)

        segment_ids = Segment.objects.values_list('id', flat=True)
        segment_png = ['{}.png'.format(x) for x in segment_ids]

        ghost_spects = [x for x in spect_files if x not in segment_png]
        ghost_masks = [x for x in mask_files if x not in segment_png]

        for x in ghost_masks:
            xpath = os.path.join(settings.MEDIA_URL, 'spect', 'mask', x)[1:]
            print('Removing {}'.format(xpath))
            os.remove(xpath)

        for x in ghost_spects:
            xpath = os.path.join(settings.MEDIA_URL, 'spect', 'fft', 'syllable', x)[1:]
            print('Removing {}'.format(xpath))
            os.remove(xpath)
