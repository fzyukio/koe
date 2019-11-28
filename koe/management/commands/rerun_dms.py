import json
import os
from logging import warning

import numpy as np

from koe.aggregator import aggregator_map
from koe.feature_utils import extract_segment_features_for_segments, aggregate_feature_values, extract_rawdata
from koe.features.feature_extract import feature_extractors
from koe.management.abstract_commands.recreate_persisted_objects import RecreateIdsPersistentObjects
from koe.models import DataMatrix
from koe.models import Segment, Feature, Aggregation
from koe.task import ConsoleTaskRunner
from koe.ts_utils import bytes_to_ndarray
from koe.ts_utils import ndarray_to_bytes


class Command(RecreateIdsPersistentObjects):
    def perform_action(self, when, remove_dead):
        for dm in DataMatrix.objects.all():
            need_reconstruct = self.check_rebuild_necessary(dm, when)

            if not need_reconstruct:
                continue

            full_sids_path = dm.get_sids_path()
            full_bytes_path = dm.get_bytes_path()
            full_cols_path = dm.get_cols_path()

            if dm.database:
                if os.path.isfile(full_sids_path):
                    sids = bytes_to_ndarray(full_sids_path, np.int32)
                else:
                    sids = Segment.objects.filter(audio_file__database=dm.database).values_list('id', flat=True)
                dbname = dm.database.name
            else:
                sids = dm.tmpdb.ids
                dbname = dm.tmpdb.name

            segments = Segment.objects.filter(id__in=sids)

            if len(segments) == 0:
                print('Skip DM #{}-{}-{}: '.format(dm.id, dbname, dm.name))

                if remove_dead:
                    print('Delete {}'.format(dm))
                    for f in [full_sids_path, full_bytes_path, full_cols_path]:
                        print('Remove binary file {}'.format(f))
                        try:
                            os.remove(f)
                        except FileNotFoundError:
                            pass
                    dm.delete()
                continue

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
