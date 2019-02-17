"""
Extract MFCC using different parameters, e.g. number of filters, frequency range, etc...
"""

import os
import pickle

from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.aggregator import aggregator_map
from koe.feature_utils import extract_segment_feature_for_audio_file
from koe.model_utils import get_or_error
from koe.models import Database, Aggregation, Segment, Feature
from koe.storage_utils import get_sids_tids
from root.utils import wav_path


def extract_mfcc_multiparams(database_name, save_dir, ncep, fmin, fmax):
    xtra_args = dict(ncep=ncep, fmin=fmin, fmax=fmax)
    features = Feature.objects.filter(name='mfcc')

    database = get_or_error(Database, dict(name__iexact=database_name))

    aggregations = Aggregation.objects.filter(enabled=True).order_by('id')
    aggregators = [aggregator_map[x.name] for x in aggregations]

    sids, tids = get_sids_tids(database)
    segments = Segment.objects.filter(id__in=sids)
    vals = list(segments.order_by('audio_file', 'start_time_ms')
                .values_list('audio_file__name', 'tid', 'start_time_ms', 'end_time_ms'))

    af_to_segments = {}
    for afname, tid, start, end in vals:
        if afname not in af_to_segments:
            af_to_segments[afname] = []
        segs_info = af_to_segments[afname]
        segs_info.append((tid, start, end))

    for feature in features:
        tid2fval = {}
        saved_file = 'database={}-feature={}-fmin={}-fmax={}-ncep={}.pkl'\
            .format(database_name, feature.name, fmin, fmax, ncep)

        saved_file_loc = os.path.join(save_dir, saved_file)
        if os.path.isfile(saved_file_loc):
            print('{} already exists. Skip'.format(saved_file_loc))
            continue
        bar = Bar('Extracting to {}'.format(saved_file_loc), max=len(af_to_segments))
        for song_name, segs_info in af_to_segments.items():
            wav_file_path = wav_path(song_name)
            __tids, __fvals = extract_segment_feature_for_audio_file(wav_file_path, segs_info, feature, **xtra_args)
            bar.next()
            for tid, fval in zip(__tids, __fvals):
                tid2fval[tid] = fval
        bar.finish()

        with open(saved_file_loc, 'wb') as f:
            pickle.dump(tid2fval, f)

        bar = Bar('Aggregating...', max=len(aggregators))
        for aggregator in aggregators:
            tid2aval = {}
            agg_saved_file = 'database={}-feature={}-aggregator={}-fmin={}-fmax={}-ncep={}.pkl'\
                .format(database_name, feature.name, aggregator.get_name(), fmin, fmax, ncep)
            agg_saved_file_loc = os.path.join(save_dir, agg_saved_file)

            if os.path.isfile(agg_saved_file_loc):
                print('{} already exists. Skip'.format(agg_saved_file_loc))
                continue

            for tid, fval in tid2fval.items():
                aggregated = aggregator.process(fval)
                tid2aval[tid] = aggregated
            bar.next()

            with open(agg_saved_file_loc, 'wb') as f:
                pickle.dump(tid2aval, f)
        bar.finish()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--save-dir', dest='save_dir', action='store', required=True)

        parser.add_argument('--ncep', dest='ncep', action='store', required=True, type=int)

        parser.add_argument('--fmin', dest='fmin', action='store', required=True, type=int)

        parser.add_argument('--fmax', dest='fmax', action='store', required=True, type=int)

    def handle(self, *args, **options):
        database_name = options['database_name']
        save_dir = options['save_dir']
        ncep = options['ncep']
        fmin = options['fmin']
        fmax = options['fmax']

        extract_mfcc_multiparams(database_name, save_dir, ncep, fmin, fmax)
