from logging import warning

import numpy as np
from django.core.management import BaseCommand

from koe.features.feature_extract import feature_extractors
from koe.aggregator import aggregator_map
from koe.feature_utils import extract_segment_features_for_segments, aggregate_feature_values
from koe.models import DataMatrix, Segment, Feature, Aggregation
from koe.task import ConsoleTaskRunner


class Command(BaseCommand):
    def handle(self, *args, **options):
        for idx, dm in enumerate(DataMatrix.objects.all()):
            if dm.database:
                segments = Segment.objects.filter(audio_file__database=dm.database)
                sids = segments.values_list('id', flat=True)
                dbname = dm.database.name
            else:
                sids = dm.tmpdb.ids
                dbname = dm.tmpdb.name

            if len(sids) == 0:
                print('Skip DM #{}-{}-{}: '.format(dm.id, dbname, dm.name))
                continue

            segments = Segment.objects.filter(id__in=sids)
            tids = np.array(segments.values_list('tid', flat=True), dtype=np.int32)

            features_ids = dm.features_hash.split('-')
            features = list(Feature.objects.filter(id__in=features_ids))

            aggregations_ids = dm.aggregations_hash.split('-')
            aggregations = Aggregation.objects.filter(id__in=aggregations_ids)

            available_feature_names = feature_extractors.keys()
            disabled_features_names = [x.name for x in features if x.name not in available_feature_names]

            if len(disabled_features_names):
                warning('DM #{}-{}-{}: Features {} are no longer available'
                        .format(dm.id, dbname, dm.name, disabled_features_names))
                features = [x for x in features if x.name in available_feature_names]

            available_aggregator_names = aggregator_map.keys()
            disabled_aggregators_names = [x.name for x in aggregations if x.name not in available_aggregator_names]

            if len(disabled_aggregators_names):
                warning('DM #{}-{}-{}: Aggregation {} are no longer available'
                        .format(dm.id, dbname, dm.name, disabled_aggregators_names))
                aggregations = [x for x in aggregations if x.name in available_aggregator_names]

            aggregators = [aggregator_map[x.name] for x in aggregations]

            runner = ConsoleTaskRunner(prefix='Extract measurement for DM #{}-{}-{}: '.format(dm.id, dbname, dm.name))
            runner.preparing()

            extract_segment_features_for_segments(runner, sids, features, force=False)
            runner.wrapping_up()

            child_runner = ConsoleTaskRunner(prefix='Aggregate measurement for DM #{}-{}-{}: '
                                                    .format(dm.id, dbname, dm.name))
            child_runner.preparing()

            aggregate_feature_values(child_runner, tids, features, aggregators)
            child_runner.wrapping_up()
            child_runner.complete()
            runner.complete()
