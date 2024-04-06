"""
Remove all ghost spectrograms / masks
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand

import numpy as np
from progress.bar import Bar

from koe.model_utils import extract_spectrogram
from koe.models import AudioFile, Database, Segment
from koe.utils import PAGE_CAPACITY


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            action="store",
            dest="database_name",
            required=False,
            type=str,
            help="Name of the database to reextract spectrogram. Omit to run for all databases",
        )

    def handle(self, database_name, *args, **options):
        if database_name is not None:
            database = Database.objects.filter(name=database_name).first()
            if database is None:
                raise Exception("Database {} not found!".format(database_name))

            segments = Segment.objects.filter(audio_file__database=database)
        else:
            segments = Segment.objects.all()

        spect_dir = os.path.join(settings.MEDIA_URL, "spect", "syllable")[1:]

        min_tid = segments.order_by("tid").first().tid
        max_tid = segments.order_by("tid").last().tid

        min_page_id = int(np.ceil(min_tid / PAGE_CAPACITY)) - 1
        max_page_id = int(np.ceil(max_tid / PAGE_CAPACITY)) + 1

        missing_segment_audio_file_info = []
        n_missing_spects = 0
        n_missing_audio_files = 0

        bar = Bar("Scanning spectrogram storage", max=max_page_id - min_page_id)

        for page_id in range(min_page_id, max_page_id + 1):
            page_dir = os.path.join(spect_dir, str(page_id))
            page_min_id = page_id * PAGE_CAPACITY + 1
            page_max_id = (page_id + 1) * PAGE_CAPACITY - 1

            if os.path.isdir(page_dir):
                spect_files = os.listdir(page_dir)
            else:
                spect_files = []
            segment_ids = segments.filter(tid__lte=page_max_id, tid__gte=page_min_id).values_list("tid", flat=True)
            segment_png = frozenset(["{}.png".format(x) for x in segment_ids])

            missing_spects = [x for x in segment_png if x not in spect_files]

            n_missing_spects += len(missing_spects)

            missing_segment_ids = [int(x[:-4]) for x in missing_spects]

            missing_segments = Segment.objects.filter(tid__in=missing_segment_ids)

            missing_segments_vl = missing_segments.values_list(
                "audio_file", "audio_file__name", "tid", "start_time_ms", "end_time_ms"
            )
            missing_segment_audio_file_ids = missing_segments.values_list("audio_file", "audio_file__name")

            new_missing_segment_audio_file_info = {(x, y): [] for x, y in missing_segment_audio_file_ids}
            for afid, afname, tid, start, end in missing_segments_vl:
                new_missing_segment_audio_file_info[(afid, afname)].append((tid, start, end))

            new_missing_segment_audio_file_info = list(new_missing_segment_audio_file_info.items())
            missing_segment_audio_file_info += new_missing_segment_audio_file_info
            n_missing_audio_files += len(new_missing_segment_audio_file_info)

            bar.next()
        bar.finish()

        print("Found {} missing spectrograms in {} audio files".format(n_missing_spects, n_missing_audio_files))

        bar = Bar("Re-extracting spectrogram", max=len(missing_segment_audio_file_info))
        for (id, name), segs_info in missing_segment_audio_file_info:
            try:
                try:
                    audio_file = AudioFile.objects.get(id=id)
                    extract_spectrogram(audio_file, segs_info)
                except:
                    print("Error re-extract segment spectrograms for file: {}".format(name))
                    raise
            except FileNotFoundError:
                print("File not found, skip")
            except Exception as e:
                print("Exception: {}".format(str(e)))
            finally:
                bar.next()
        bar.finish()
