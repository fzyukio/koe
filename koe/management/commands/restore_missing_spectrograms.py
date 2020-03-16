"""
Remove all ghost spectrograms / masks
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.model_utils import extract_spectrogram
from koe.models import Segment, AudioFile
from koe.utils import PAGE_CAPACITY


class Command(BaseCommand):
    def handle(self, *args, **options):
        spect_dir = os.path.join(settings.MEDIA_URL, 'spect', 'syllable')[1:]

        missing_segment_audio_file_info = []
        pages = os.listdir(spect_dir)
        for page in pages:
            try:
                page = int(page)
            except ValueError:
                continue
            page_min_id = page * PAGE_CAPACITY
            page_max_id = page_min_id + PAGE_CAPACITY - 1

            spect_files = os.listdir(os.path.join(spect_dir, str(page)))
            segment_ids = Segment.objects.filter(tid__lte=page_max_id, tid__gte=page_min_id)\
                .values_list('tid', flat=True)
            segment_png = frozenset(['{}.png'.format(x) for x in segment_ids])

            missing_spects = [x for x in segment_png if x not in spect_files]
            missing_segment_ids = [x[:-4] for x in missing_spects]

            missing_segments = Segment.objects.filter(tid__in=missing_segment_ids)
            missing_segment_audio_file_ids = missing_segments.values_list('audio_file', flat=True).distinct()
            missing_segment_audio_file = AudioFile.objects.filter(id__in=missing_segment_audio_file_ids)
            missing_segment_audio_file_info += list(missing_segment_audio_file.values_list('id', 'name'))

        # missing_segment_audio_file = AudioFile.objects.filter(name='M23 16-8-19-SR.19.ch01-02.191210.130453.28.')

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
