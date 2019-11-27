import json
import os
from logging import warning

import numpy as np
from django.core.management import BaseCommand

from koe import binstorage3 as bs
from koe.aggregator import aggregator_map
from koe.feature_utils import extract_segment_features_for_segments, aggregate_feature_values, extract_rawdata
from koe.features.feature_extract import feature_extractors, feature_map
from koe.models import DataMatrix, Segment, Feature, Aggregation
from koe.storage_utils import get_storage_loc_template
from koe.task import ConsoleTaskRunner
from koe.ts_utils import ndarray_to_bytes


def reextract_dm(dm, only_missing=False):
    if dm.database:
        segments = Segment.objects.filter(audio_file__database=dm.database)
        sids = segments.values_list('id', flat=True)
        dbname = dm.database.name
    else:
        sids = dm.tmpdb.ids
        dbname = dm.tmpdb.name

    full_sids_path = dm.get_sids_path()
    full_bytes_path = dm.get_bytes_path()
    full_cols_path = dm.get_cols_path()

    file_missing = True
    if os.path.isfile(full_sids_path) and os.path.isfile(full_bytes_path) and os.path.isfile(full_cols_path):
        file_missing = False

    need_extraction = False
    if not only_missing or file_missing:
        need_extraction = True

    if not need_extraction:
        return

    segments = Segment.objects.filter(id__in=sids)

    if len(segments) != len(sids):
        warning('Datamatrix {}{}{} contains IDs that have been removed.'.format(dm.id, dbname, dm.name))

    if len(segments) == 0:
        print('Skip DM #{}-{}-{}: '.format(dm.id, dbname, dm.name))
        return

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

    data, col_inds = extract_rawdata(tids, features, aggregators)

    ndarray_to_bytes(data, full_bytes_path)
    ndarray_to_bytes(np.array(sids, dtype=np.int32), full_sids_path)

    with open(full_cols_path, 'w', encoding='utf-8') as f:
        json.dump(col_inds, f)

    dm.ndims = data.shape[1]
    dm.save()


def reextract_by_tids(features, aggregators):
    for feature in features:
        storage_loc_template = get_storage_loc_template()
        storage_loc = storage_loc_template.format(feature.name)

        if not os.path.isdir(storage_loc):
            continue

        existing_tids = bs.retrieve_ids(storage_loc)
        sids = Segment.objects.filter(tid__in=existing_tids).values_list('id', flat=True)
        nsids = len(sids)

        prefix = 'Re-extract measurement for feature {}, nids = {}'.format(feature.name, nsids)
        runner = ConsoleTaskRunner(prefix=prefix)
        runner.preparing()
        extract_segment_features_for_segments(runner, sids, [feature], force=False)
        runner.wrapping_up()
        runner.complete()

        for aggregator in aggregators:
            fa_storage_loc_template = os.path.join(storage_loc, '{}')
            fa_storage_loc = fa_storage_loc_template.format(aggregator.name)

            if not os.path.isdir(fa_storage_loc):
                continue

            tids = bs.retrieve_ids(fa_storage_loc)
            ntids = len(tids)

            prefix = 'Apply aggregation {}, nids = {}'.format(aggregator.name, ntids)
            runner = ConsoleTaskRunner(prefix=prefix)
            runner.preparing()

            aggregate_feature_values(runner, tids, [feature], [aggregator], force=False)
            runner.wrapping_up()
            runner.complete()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--use-dm', action='store_true', dest='use_dm', default=False)
        parser.add_argument('--use-tid', action='store_true', dest='use_tid', default=False)
        parser.add_argument('--only-missing', action='store_true', dest='only_missing', default=False)

    def handle(self, *args, **options):
        use_dm = options['use_dm']
        use_tid = options['use_tid']
        only_missing = options['only_missing']

        features = list(feature_map.values())

        aggregations = Aggregation.objects.filter(enabled=True).order_by('id')
        aggregators = [aggregator_map[x.name] for x in aggregations]

        if use_dm and use_tid:
            raise Exception('Use either --use-dm or --use-tid')

        if use_dm:
            for dm in DataMatrix.objects.all():
                reextract_dm(dm, only_missing)
        else:
            reextract_by_tids(features, aggregators)
