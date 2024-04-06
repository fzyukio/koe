r"""
Run this to generate a CSV file that has two columns: id and label.
ID=ids of the segments, label=Label given to that segment

e.g:

- python manage.py segment_select --database-name=bellbirds --owner=superuser --csv-file=/tmp/bellbirds.csv \
                                  --startswith=LBI --label-level=label_family --labels-to-ignore="Click;Stutter"
  --> Find segments of Bellbirds database, where the files start with LBI and family labels made by superuser, ignore
      all segments that are labelled 'Click' or 'Stutter', save to file /tmp/bellbirds.csv
"""

import os

from django.core.management.base import BaseCommand

import numpy as np
import pydub
from progress.bar import Bar

from koe.model_utils import (
    exclude_no_labels,
    get_labels_by_sids,
    get_or_error,
    select_instances,
)
from koe.models import Database, Segment
from koe.spect_utils import (
    extract_global_min_max,
    extractors,
    normalise_all,
    save_global_min_max,
)
from koe.utils import get_kfold_indices, wav_path
from root.models import User
from root.utils import ensure_parent_folder_exists, mkdirp


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--database-name",
            action="store",
            dest="database_name",
            required=True,
            type=str,
            help="E.g Bellbird, Whale, ..., case insensitive",
        )

        parser.add_argument(
            "--annotator",
            action="store",
            dest="annotator_name",
            default="superuser",
            type=str,
            help="Name of the person who labels this dataset, case insensitive",
        )

        parser.add_argument(
            "--label-level",
            action="store",
            dest="label_level",
            default="label",
            type=str,
            help="Level of labelling to use",
        )

        parser.add_argument(
            "--min-occur",
            action="store",
            dest="min_occur",
            default=2,
            type=int,
            help="Ignore syllable classes that have less than this number of instances",
        )

        parser.add_argument(
            "--num-instances",
            action="store",
            dest="num_instances",
            default=None,
            type=int,
            help="Number of instances per class to extract. Must be >= min_occur",
        )

        parser.add_argument(
            "--save-to",
            action="store",
            dest="save_to",
            required=True,
            type=str,
        )

        parser.add_argument(
            "--format",
            action="store",
            dest="format",
            default="wav",
            type=str,
        )

        parser.add_argument("--normalised", action="store_true", dest="normalised", default=False)

    def handle(self, *args, **options):
        database_name = options["database_name"]
        annotator_name = options["annotator_name"]
        label_level = options["label_level"]
        save_to = options["save_to"]
        format = options["format"]
        min_occur = options["min_occur"]
        num_instances = options["num_instances"]
        normalised = options["normalised"]

        if num_instances is not None:
            assert num_instances >= min_occur, "num_instances must be >= min_occur"

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        segments = Segment.objects.filter(audio_file__database=database)

        sids = np.array(list(segments.order_by("id").values_list("id", flat=True)))

        labels, no_label_ids = get_labels_by_sids(sids, label_level, annotator, min_occur)
        if len(no_label_ids) > 0:
            sids, _, labels = exclude_no_labels(sids, None, labels, no_label_ids)

        if num_instances:
            sids, _, labels = select_instances(sids, None, labels, num_instances)

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        fold_indices = get_kfold_indices(enum_labels, min_occur)

        segments_info = {
            sid: (label, label_enum, fold_ind)
            for sid, label, label_enum, fold_ind in zip(sids, labels, enum_labels, fold_indices)
        }

        segs = Segment.objects.filter(id__in=sids)

        audio_file_dict = {}
        for seg in segs:
            af = seg.audio_file
            if af in audio_file_dict:
                info = audio_file_dict[af]
            else:
                info = []
                audio_file_dict[af] = info
            info.append((seg.id, seg.start_time_ms, seg.end_time_ms))

        audio_info = []

        bar = Bar("Exporting segments ...", max=len(segs))
        metadata_file_path = os.path.join(save_to, "metadata.tsv")

        extractor = extractors.get(format, None)

        for af, info in audio_file_dict.items():
            wav_file_path = wav_path(af)
            fullwav = pydub.AudioSegment.from_wav(wav_file_path)

            for id, start, end in info:
                label, label_enum, fold_ind = segments_info[id]

                audio_segment = fullwav[start:end]

                filename = "{}.{}".format(id, format)

                filepath = os.path.join(save_to, filename)
                ensure_parent_folder_exists(filepath)

                if not os.path.isfile(filepath):
                    if extractor is not None:
                        database = af.database
                        extractor(
                            wav_file_path,
                            fs=af.fs,
                            start=start,
                            end=end,
                            nfft=database.nfft,
                            noverlap=database.noverlap,
                            filepath=filepath,
                        )
                    else:
                        with open(filepath, "wb") as f:
                            audio_segment.export(f, format=format)

                audio_info.append((id, filename, label, label_enum, fold_ind))

                bar.next()

        with open(metadata_file_path, "w") as f:
            f.write("id\tfilename\tlabel\tlabel_enum\tfold\n")
            for id, filename, label, label_enum, fold_ind in audio_info:
                f.write("{}\t{}\t{}\t{}\t{}\n".format(id, filename, label, label_enum, fold_ind))

        bar.finish()

        if normalised:
            norm_folder = os.path.join(save_to, "normalised")
            mkdirp(norm_folder)
            global_min, global_max = extract_global_min_max(save_to, format)
            save_global_min_max(norm_folder, global_min, global_max)
            normalise_all(save_to, norm_folder, format, global_min, global_max)
