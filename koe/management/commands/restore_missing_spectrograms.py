"""
Remove all ghost spectrograms / masks
"""
import os

import numpy as np

from django.conf import settings
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.model_utils import extract_spectrogram
from koe.models import Segment, AudioFile
from koe.utils import PAGE_CAPACITY


class Command(BaseCommand):
    def handle(self, *args, **options):
        spect_dir = os.path.join(settings.MEDIA_URL, 'spect', 'syllable')[1:]

        min_tid = Segment.objects.order_by('tid').first().tid
        max_tid = Segment.objects.order_by('tid').last().tid

        min_page_id = int(np.ceil(min_tid / PAGE_CAPACITY))
        max_page_id = int(np.ceil(max_tid / PAGE_CAPACITY)) + 1

        missing_segment_audio_file_info = []

        for page_id in range(min_page_id, max_page_id + 1):
            page_dir = os.path.join(spect_dir, str(page_id))
            page_min_id = (page_id - 1) * PAGE_CAPACITY + 1
            page_max_id = page_id * PAGE_CAPACITY

            if os.path.isfile(page_dir):
                spect_files = os.listdir(page_dir)
            else:
                spect_files = []
            segment_ids = Segment.objects.filter(tid__lte=page_max_id, tid__gte=page_min_id)\
                .values_list('tid', flat=True)
            segment_png = frozenset(['{}.png'.format(x) for x in segment_ids])

            missing_spects = [x for x in segment_png if x not in spect_files]
            missing_segment_ids = [x[:-4] for x in missing_spects]

            missing_segments = Segment.objects.filter(tid__in=missing_segment_ids)
            missing_segment_audio_file_ids = missing_segments.values_list('audio_file', flat=True).distinct()
            missing_segment_audio_file = AudioFile.objects.filter(id__in=missing_segment_audio_file_ids)
            missing_segment_audio_file_info += list(missing_segment_audio_file.values_list('id', 'name'))

        print('Found missing spectrograms in {} audio files'.format(len(missing_segment_audio_file_info)))

        bar = Bar('Re-extracting spectrogram', max=len(missing_segment_audio_file_info))
        for id, name in missing_segment_audio_file_info:
            try:
                try:
                    extract_spectrogram(id)
                except:
                    print('Error re-extract segment spectrograms for file: {}'.format(name))
                    raise
            except FileNotFoundError:
                print('File not found, skip')
            except Exception as e:
                print('Exception: {}'.format(str(e)))
            finally:
                bar.next()
        bar.finish()
