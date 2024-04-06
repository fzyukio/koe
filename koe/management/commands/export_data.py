r"""
Run this to generate a CSV file that has two columns: id and label.
ID=ids of the segments, label=Label given to that segment

e.g:

- python manage.py segment_select --database-name=bellbirds --owner=superuser --csv-file=/tmp/bellbirds.csv \
                                  --startswith=LBI --label-level=label_family --labels-to-ignore="Click;Stutter"
  --> Find segments of Bellbirds database, where the files start with LBI and family labels made by superuser, ignore
      all segments that are labelled 'Click' or 'Stutter', save to file /tmp/bellbirds.csv
"""

import csv
import os

from django.core.management.base import BaseCommand

import pydub
from progress.bar import Bar

from koe.models import Segment
from koe.utils import wav_path
from root.utils import mkdirp


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="store",
            dest="segment_csv",
            required=True,
            type=str,
            help="CSV file containing IDs + labels of the segments to be extracted",
        )

        parser.add_argument(
            "--folder",
            action="store",
            dest="folder",
            required=True,
            type=str,
        )

    def handle(self, *args, **options):
        segment_csv = options["segment_csv"]
        folder = options["folder"]
        mkdirp(folder)

        with open(segment_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            supplied_fields = reader.fieldnames

            # The first field is always id, the second field is always the primary label type
            primary_label_level = supplied_fields[1]

            sid_to_label = {int(row["id"]): row[primary_label_level] for row in reader}

        sids = sid_to_label.keys()
        audio_file_dict = {}
        for segment in Segment.objects.filter(id__in=sids):
            af = segment.audio_file
            if af in audio_file_dict:
                info = audio_file_dict[af]
            else:
                info = []
                audio_file_dict[af] = info
            info.append((segment.id, segment.start_time_ms, segment.end_time_ms))

        bar = Bar("Exporting segments ...", max=len(sid_to_label))
        for af, info in audio_file_dict.items():
            wav_file_path = wav_path(af)
            fullwav = pydub.AudioSegment.from_wav(wav_file_path)

            for id, start, end in info:
                audio_segment = fullwav[start:end]

                filename = "{}.wav".format(id)
                filepath = os.path.join(folder, filename)
                with open(filepath, "wb") as f:
                    audio_segment.export(f, format="wav")
                bar.next()
        bar.finish()
