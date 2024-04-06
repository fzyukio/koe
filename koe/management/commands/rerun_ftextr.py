import os

from django.core.management import BaseCommand

from koe import binstorage3 as bs
from koe.aggregator import aggregator_map
from koe.feature_utils import aggregate_feature_values, extract_segment_features_for_segments
from koe.features.feature_extract import feature_map
from koe.models import Aggregation, Segment
from koe.storage_utils import get_storage_loc_template
from koe.task import ConsoleTaskRunner


class Command(BaseCommand):
    def handle(self, *args, **options):
        features = list(feature_map.values())

        aggregations = Aggregation.objects.filter(enabled=True).order_by("id")
        aggregators = [aggregator_map[x.name] for x in aggregations]

        for feature in features:
            storage_loc_template = get_storage_loc_template()
            storage_loc = storage_loc_template.format(feature.name)

            if not os.path.isdir(storage_loc):
                continue

            existing_tids = bs.retrieve_ids(storage_loc)
            sids = Segment.objects.filter(tid__in=existing_tids).values_list("id", flat=True)
            nsids = len(sids)

            prefix = "Re-extract measurement for feature {}, nids = {}".format(feature.name, nsids)
            runner = ConsoleTaskRunner(prefix=prefix)
            runner.preparing()
            extract_segment_features_for_segments(runner, sids, [feature], force=False)
            runner.wrapping_up()
            runner.complete()

            for aggregator in aggregators:
                fa_storage_loc_template = os.path.join(storage_loc, "{}")
                fa_storage_loc = fa_storage_loc_template.format(aggregator.name)

                if not os.path.isdir(fa_storage_loc):
                    continue

                tids = bs.retrieve_ids(fa_storage_loc)
                ntids = len(tids)

                prefix = "Apply aggregation {}, nids = {}".format(aggregator.name, ntids)
                runner = ConsoleTaskRunner(prefix=prefix)
                runner.preparing()

                aggregate_feature_values(runner, tids, [feature], [aggregator], force=False)
                runner.wrapping_up()
                runner.complete()
