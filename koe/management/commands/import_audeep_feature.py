r"""
Run this to generate a CSV file that has two columns: id and label.
ID=ids of the segments, label=Label given to that segment

e.g:

- python manage.py segment_select --database-name=bellbirds --owner=superuser --csv-file=/tmp/bellbirds.csv \
                                  --startswith=LBI --label-level=label_family --labels-to-ignore="Click;Stutter"
  --> Find segments of Bellbirds database, where the files start with LBI and family labels made by superuser, ignore
      all segments that are labelled 'Click' or 'Stutter', save to file /tmp/bellbirds.csv
"""

import json
import os

from django.core.management.base import BaseCommand
from django.db.models import Case, When

import numpy as np
from audeep.backend.data import data_set
from pathlib2 import Path

from koe.model_utils import get_or_error
from koe.models import Database, DataMatrix, Segment
from koe.ts_utils import ndarray_to_bytes


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            action="store",
            dest="path",
            required=True,
            type=str,
            help="Path to audeep generated's representations.nc file ",
        )

        parser.add_argument(
            "--database",
            action="store",
            dest="database_name",
            required=True,
            type=str,
            help="E.g Bellbird, Whale, ..., case insensitive",
        )

        parser.add_argument(
            "--dm-name",
            action="store",
            dest="dm_name",
            required=True,
            type=str,
            help="E.g Bellbird, Whale, ..., case insensitive",
        )

    def handle(self, *args, **options):
        path = options["path"]
        if not os.path.isfile(path):
            raise Exception("File {} not found".format(path))

        database_name = options["database_name"]
        dm_name = options["dm_name"]
        database = get_or_error(Database, dict(name__iexact=database_name))

        dataset = data_set.load(Path(path))
        features = dataset.features
        filenames = dataset.filenames
        sids = [int(x[:-4]) for x in filenames]

        nobs, ndims = dataset.features.shape

        preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(sids)])
        segments = Segment.objects.filter(id__in=sids).order_by(preserved)
        tids = segments.values_list("tid", flat=True)

        col_inds = {"s2s_autoencoded": [0, ndims]}

        dm = DataMatrix(database=database)
        dm.name = dm_name
        dm.ndims = ndims
        dm.features_hash = "s2s_autoencoded"
        dm.aggregations_hash = ""
        dm.save()

        full_sids_path = dm.get_sids_path()
        full_tids_path = dm.get_tids_path()
        full_bytes_path = dm.get_bytes_path()
        full_cols_path = dm.get_cols_path()

        ndarray_to_bytes(features, full_bytes_path)
        ndarray_to_bytes(np.array(sids, dtype=np.int32), full_sids_path)
        ndarray_to_bytes(np.array(tids, dtype=np.int32), full_tids_path)

        with open(full_cols_path, "w", encoding="utf-8") as f:
            json.dump(col_inds, f)
