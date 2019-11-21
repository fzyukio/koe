from logging import warning

import os
import numpy as np
from django.core.management import BaseCommand

from koe.features.feature_extract import feature_extractors, feature_map
from koe.aggregator import aggregator_map
from koe.feature_utils import extract_segment_features_for_segments, aggregate_feature_values
from koe.models import DataMatrix, Segment, Feature, Aggregation
from koe.task import ConsoleTaskRunner
from koe import binstorage3 as bs

from root.utils import mkdirp
from koe.storage_utils import get_storage_loc_template


def reextract_dm(dm, skip_features=False, skip_aggregations=False):
    if dm.database:
        segments = Segment.objects.filter(audio_file__database=dm.database)
        sids = segments.values_list('id', flat=True)
        dbname = dm.database.name
    else:
        sids = dm.tmpdb.ids
        dbname = dm.tmpdb.name

    if len(sids) == 0:
        print('Skip DM #{}-{}-{}: '.format(dm.id, dbname, dm.name))
        return

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

    if not skip_features:
        runner = ConsoleTaskRunner(prefix='Extract measurement for DM #{}-{}-{}: '.format(dm.id, dbname, dm.name))
        runner.preparing()
        extract_segment_features_for_segments(runner, sids, features, force=False)
        runner.wrapping_up()

    if not skip_aggregations:
        child_runner = ConsoleTaskRunner(prefix='Aggregate measurement for DM #{}-{}-{}: '
                                         .format(dm.id, dbname, dm.name))
        child_runner.preparing()

        aggregate_feature_values(child_runner, tids, features, aggregators)
        child_runner.wrapping_up()
        child_runner.complete()

    if not skip_features:
        runner.complete()


def reextract_by_tids(features, aggregators):
    for feature in features:
        storage_loc_template = get_storage_loc_template()
        storage_loc = storage_loc_template.format(feature.name)

        if not os.path.isdir(storage_loc):
            continue

        existing_tids = bs.retrieve_ids(storage_loc)
        sids = Segment.objects.filter(tid__in=existing_tids).values_list('id', flat=True)
        nsids = len(sids)

        runner = ConsoleTaskRunner(prefix='Re-extract measurement for feature {}, nids = {}'.format(feature.name, nsids))
        runner.preparing()
        extract_segment_features_for_segments(runner, sids, [feature], force=False)
        runner.wrapping_up()
        runner.complete()

        for aggregator in aggregators:
            fa_storage_loc_template = os.path.join(storage_loc, '{}')
            fa_storage_loc = fa_storage_loc_template.format(aggregator.name)

            if not os.path.isdir(fa_storage_loc):
                continue
                continue

            tids = bs.retrieve_ids(fa_storage_loc)
            ntids = len(tids)

            runner = ConsoleTaskRunner(prefix='Apply aggregation {}, nids = {}'.format(aggregator.name, ntids))
            runner.preparing()

            aggregate_feature_values(runner, tids, [feature], [aggregator], force=False)
            runner.wrapping_up()
            runner.complete()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--use-dm', action='store_true', dest='use_dm', default=False)
        parser.add_argument('--use-tid', action='store_true', dest='use_tid', default=False)

        # parser.add_argument('--features', action='store', dest='features', default=None, type=str)
        # parser.add_argument('--aggregators', action='store', dest='aggregators', default=None, type=str)

    def handle(self, *args, **options):
        use_dm = options['use_dm']
        use_tid = options['use_tid']
        # features_to_use = options['features']
        # aggregators_to_use = options['aggregators']

        # if features_to_use:
        #     features_to_use = list(features_to_use.split(','))
        #     features = [feature_map[x] for x in features_to_use]
        # else:
        features = list(feature_map.values())

        aggregations = Aggregation.objects.filter(enabled=True).order_by('id')
        # if aggregators_to_use:
        #     aggregators_to_use = list(aggregators_to_use.split(','))
        #     aggregators = [aggregator_map[x] for x in aggregators_to_use]
        # else:
        aggregators = [aggregator_map[x.name] for x in aggregations]

        if use_dm and use_tid:
            raise Exception('Use either --use-dm or --use-tid')

        if use_dm:
            for dm in DataMatrix.objects.all():
                reextract_dm(dm)
        else:
            reextract_by_tids(features, aggregators)

