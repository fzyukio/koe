r"""
Run to extract features of given segment ID and export the feature matrix with segment labels to a matlab file

e.g.
python manage.py extract_features --csv=/tmp/bellbirds.csv --h5file=bellbird-lbi.h5 --matfile=/tmp/mt-lbi.mat \
                                  --features="frequency_modulation;spectral_continuity;mean_frequency"

--> extracts full features (see features/feature_extract.py for the full list)
            of segments in file /tmp/bellbirds.csv (created by segment_select)
            stores the features in bellbird-lbi.h5
            then use three features (frequency_modulation;spectral_continuity;mean_frequency) (aggregated by mean,
            median, std) to construct a feature matrix (9 dimensions). Store this matrix with the labels (second column
            in /tmp/bellbirds.csv) to file /tmp/mt-lbi.mat
"""
import os
import pickle
from logging import warning

import csv
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import F
from progress.bar import Bar

from koe import binstorage
from koe.aggregator import enabled_aggregators
from koe.features.feature_extract import feature_extractors
from koe.features.feature_extract import feature_whereabout as feature_groups
from koe.features.feature_extract import features as full_features
from koe.model_utils import get_or_error
from koe.models import Feature, Segment, Database
from koe.utils import get_wav_info
from root.utils import wav_path, data_path, ensure_parent_folder_exists, mkdirp

nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap


# @profile
def extract_segment_features_for_audio_file(wav_file_path, segs_info, features, tid2fvals):
    fs, length = get_wav_info(wav_file_path)

    duration_ms = length * 1000 / fs
    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=fs, start=0, end=None,
                win_length=win_length, center=False)

    def add_feature_value(tid, val):
        if tid not in tid2fvals:
            fvals = []
            tid2fvals[tid] = fvals
        else:
            fvals = tid2fvals[tid]

        fvals.append(val)

    for fidx, feature in enumerate(features):
        extractor = feature_extractors[feature.name]

        if feature.is_fixed_length:
            for tid, beg, end in segs_info:
                args['start'] = beg
                args['end'] = end
                feature_value = extractor(args)
                add_feature_value(tid, feature_value)
        else:
            args['start'] = 0
            args['end'] = None
            audio_file_feature_value = extractor(args)

            if feature.is_one_dimensional:
                feature_length = max(audio_file_feature_value.shape)
                audio_file_feature_value = audio_file_feature_value.reshape((1, feature_length))
            else:
                feature_length = audio_file_feature_value.shape[1]

            for tid, beg, end in segs_info:
                beg_idx = max(0, int(np.floor(beg * feature_length / duration_ms)))
                end_idx = min(feature_length, int(np.ceil(end * feature_length / duration_ms)))
                if end_idx == beg_idx:
                    warning('Segment is too short - result might be not meaningful')
                    end_idx = beg_idx + 1

                if audio_file_feature_value.ndim == 2:
                    feature_value = audio_file_feature_value[:, beg_idx:end_idx]
                else:
                    feature_value = audio_file_feature_value[beg_idx:end_idx]

                add_feature_value(tid, feature_value)


def extract_segment_features_for_segments(sids, features):
    segments = Segment.objects.filter(id__in=sids)

    vals = segments.order_by('audio_file', 'start_time_ms')\
        .values_list('audio_file__name', 'tid', 'start_time_ms', 'end_time_ms')
    af_to_segments = {}

    for name, tid, start, end in vals:
        if name not in af_to_segments:
            af_to_segments[name] = []
        af_to_segments[name].append((tid, start, end))

    num_audio_files = len(af_to_segments)

    bar = Bar('Extracting...', max=num_audio_files)

    tid2fvals = {}
    for song_name, segs_info in af_to_segments.items():
        wav_file_path = wav_path(song_name)
        extract_segment_features_for_audio_file(wav_file_path, segs_info, features, tid2fvals)
        bar.next()

    bar.finish()
    return tid2fvals


# @profile
def aggregate_feature_values(sids, f2bs, fa2bs, features, ftgroup_name, aggregators, aggregators_name):
    """
    Compress all feature sequences into fixed-length vectors
    :param sid_to_label:
    :param h5file:
    :param features:
    :return:
    """
    if features is None or len(features) == 0:
        raise Exception('must provide non-empty list of features')

    segment_info = Segment.objects\
        .filter(id__in=sids)\
        .annotate(duration=F('end_time_ms') - F('start_time_ms')).order_by('duration')

    n_calculations = sum([0 if f.is_fixed_length else len(aggregators) for f in features]) * len(sids)
    attrs = segment_info.values_list('tid', 'duration', 'audio_file__fs')

    duration2segs = {}
    for tid, duration, fs in attrs:
        if duration not in duration2segs:
            segs = [[], []]
            duration2segs[duration] = segs
        else:
            segs = duration2segs[duration]
        segs[0].append(tid)
        segs[1].append(fs)

    bar = Bar('Extract features type {}, aggrenator type {}'.format(ftgroup_name, aggregators_name),
              max=n_calculations)

    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=None, start=None, end=None, win_length=win_length,
                center=False)

    all_tids = []
    all_aggregated_values = {}

    for duration, (tids, fss) in duration2segs.items():
        all_tids += tids

        tids = np.array(tids, dtype=np.int32)

        for feature in features:
            if feature not in all_aggregated_values:
                all_aggregated_values_this = {}
                all_aggregated_values[feature] = all_aggregated_values_this
            else:
                all_aggregated_values_this = all_aggregated_values[feature]

            f_idf, f_vlf = f2bs[feature]
            values = binstorage.retrieve(tids, f_idf, f_vlf)

            # aggregated_values = {}

            for tid, fs, value in zip(tids, fss, values):
                args['fs'] = fs

                if not feature.is_fixed_length:
                    if value.ndim == 2:
                        nframes = value.shape[1]
                    else:
                        nframes = value.shape[0]

                    min_nsamples = nfft + (nframes - 1) * stepsize
                    args['nsamples'] = min_nsamples

                    for aggregator in aggregators:
                        if aggregator not in all_aggregated_values_this:
                            all_aggregated_values_this[aggregator] = []

                        if aggregator.is_chirpy():
                            aggregated = aggregator.process(value, args=args, feature=feature)
                        else:
                            aggregated = aggregator.process(value)

                        all_aggregated_values_this[aggregator].append(aggregated)
                        bar.next()

    all_tids = np.array(all_tids, dtype=np.int32)
    for feature in features:
        if feature.is_fixed_length:
            continue
        for aggregator in aggregators:
            fa_idf, fa_vlf = fa2bs[feature][aggregator]

            try:
                binstorage.store(all_tids, all_aggregated_values[feature][aggregator], fa_idf, fa_vlf)
            except Exception as e:
                saved_path_ = '/tmp/agg-{}-{}.f2vals'.format(feature.name, aggregator.get_name())
                with open(saved_path_, 'wb') as f:
                    pickle.dump(dict(tids=all_tids, values=all_aggregated_values[feature][aggregator]), f)
                print('Error occured, saved to {}'.format(saved_path_))
                raise e
    bar.finish()


def get_segment_ids_and_labels(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        supplied_fields = reader.fieldnames

        # The first field is always id, the second field is always the primary label type
        primary_label_level = supplied_fields[1]

        return {int(row['id']): row[primary_label_level] for row in reader}


def extract_tids_fvals(tid2fvals, features):
    tids = np.array(list(tid2fvals.keys()))
    tids.sort()

    vals_per_feature = [[] for feature in features]
    for tid in tids:
        fvals = tid2fvals[tid]
        for idx, val in enumerate(fvals):
            vals_per_feature[idx].append(val)

    f2vals = {x: y for x, y in zip(features, vals_per_feature)}
    return tids, f2vals


def store_feature_values(ids, feature, values_arr):
    index_filename = data_path('binary/features', '{}.idx'.format(feature.name), for_url=False)
    value_filename = data_path('binary/features', '{}.val'.format(feature.name), for_url=False)

    ensure_parent_folder_exists(index_filename)
    binstorage.store(ids, values_arr, index_filename, value_filename)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

    def handle(self, *args, **options):
        database_name = options['database_name']
        database = get_or_error(Database, dict(name__iexact=database_name))

        segments = Segment.objects.filter(audio_file__database=database)
        sids = segments.values_list('id', flat=True)
        saved_path = '/tmp/saved.f2vals'
        if os.path.isfile(saved_path):
            with open(saved_path, 'rb') as f:
                saved = pickle.load(f)
                tids = saved['tids']
                f2vals = saved['f2vals']
        else:
            tid2fvals = extract_segment_features_for_segments(sids, full_features)
            tids, f2vals = extract_tids_fvals(tid2fvals, full_features)
            with open(saved_path, 'wb') as f:
                pickle.dump(dict(tids=tids, f2vals=f2vals), f, pickle.HIGHEST_PROTOCOL)

        # feature to binstorage's files
        f2bs = {}
        # feature+aggregation to binstorage's files
        fa2bs = {}

        for feature in full_features:
            feature_name = feature.name
            index_filename = data_path('binary/features', '{}.idx'.format(feature_name), for_url=False)
            value_filename = data_path('binary/features', '{}.val'.format(feature_name), for_url=False)
            f2bs[feature] = (index_filename, value_filename)

            values_arr = f2vals[feature]
            ensure_parent_folder_exists(index_filename)
            try:
                binstorage.store(tids, values_arr, index_filename, value_filename)
            except Exception as e:
                saved_path_ = '/tmp/saved-{}.f2vals'.format(feature.name)
                with open(saved_path_, 'wb') as f:
                    pickle.dump(dict(tids=tids, values_arr=values_arr), f)
                print('Error occured, saved to {}'.format(saved_path_))
                raise e

            if feature not in fa2bs:
                fa2bs[feature] = {}
            for aggregators in enabled_aggregators.values():
                for aggregator in aggregators:
                    aggregator_name = aggregator.get_name()
                    folder = os.path.join('binary', 'features', feature_name)
                    mkdirp(os.path.join(settings.MEDIA_URL, folder)[1:])

                    index_filename = data_path(folder, '{}.idx'.format(aggregator_name), for_url=False)
                    value_filename = data_path(folder, '{}.val'.format(aggregator_name), for_url=False)
                    fa2bs[feature][aggregator] = (index_filename, value_filename)

        for aggregators_name, aggregators in enabled_aggregators.items():

            for ftgroup_module, ftgroup in feature_groups.items():
                if isinstance(ftgroup_module, str):
                    ftgroup_name = ftgroup_module
                else:
                    ftgroup_name = ftgroup_module.__name__[len('koe.features.'):]

                selected_features = list(Feature.objects.filter(name__in=[ft[0] for ft in ftgroup]))

                aggregate_feature_values(sids, f2bs, fa2bs, selected_features, ftgroup_name, aggregators,
                                         aggregators_name)
