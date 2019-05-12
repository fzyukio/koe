"""
Remove all ghost spectrograms / masks
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from koe.model_utils import extract_spectrogram
from koe.models import Segment, AudioFile


class Command(BaseCommand):

    def handle(self, *args, **options):
        spect_dir = os.path.join(settings.MEDIA_URL, 'spect', 'fft', 'syllable')[1:]

        spect_files = os.listdir(spect_dir)

        segment_ids = Segment.objects.values_list('tid', flat=True)
        segment_png = frozenset(['{}.png'.format(x) for x in segment_ids])

        missing_spects = [x for x in segment_png if x not in spect_files]
        missing_segment_ids = [x[:-4] for x in missing_spects]

        missing_segments = Segment.objects.filter(tid__in=missing_segment_ids)
        missing_segment_audio_file_ids = missing_segments.values_list('audio_file', flat=True).distinct()
        missing_segment_audio_file = AudioFile.objects.filter(id__in=missing_segment_audio_file_ids)

        for audio_file in missing_segment_audio_file:
            print('Re-extract segment spectrograms for file: {}'.format(audio_file.name))
            try:
                extract_spectrogram(audio_file.id)
            except FileNotFoundError as e:
                print('File not found, skip')
