"""
Start with all syllables belonging to one class, then split them by distance until each syllable is one class.
At each step, produce sequences, construct a graph and extract features from the graph
"""

from django.core.management import BaseCommand

import numpy as np

from koe.aggregator import aggregator_map
from koe.feature_utils import aggregate_feature_values, extract_segment_features_for_segments
from koe.features.feature_extract import feature_map
from koe.model_utils import get_or_error
from koe.models import Aggregation, Database, Segment
from koe.task import ConsoleTaskRunner


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

    def handle(self, *args, **options):
        database_name = options["database_name"]
        database = get_or_error(Database, dict(name__iexact=database_name))

        runner = ConsoleTaskRunner(prefix="Extract measurement for database: " + database_name)
        runner.preparing()
        # segments = Segment.objects.filter(audio_file__database=database,
        #                                   audio_file__name='TMI_2015_11_26_CHJ051_01_F.OK.HR-RM.(A)')
        segments = Segment.objects.filter(audio_file__database=database)
        sids = list(segments.values_list("id", flat=True))

        if len(sids) == 0:
            return

        features = list(feature_map.values())
        # features = [feature_map['spectral_rolloff'], feature_map['spectral_flatness']]
        aggregations = Aggregation.objects.filter(enabled=True)
        aggregators = [aggregator_map[x.name] for x in aggregations]

        segments = Segment.objects.filter(id__in=sids)
        tids = np.array(segments.values_list("tid", flat=True), dtype=np.int32)

        extract_segment_features_for_segments(runner, sids, features, force=False)
        runner.wrapping_up()

        child_runner = ConsoleTaskRunner(prefix="Aggregate measurement for database: " + database.name)
        child_runner.preparing()

        aggregate_feature_values(child_runner, tids, features, aggregators)
        child_runner.wrapping_up()
        child_runner.complete()
        runner.complete()
