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
import json
import os
import time
import uuid

import h5py
import numpy as np
from django.core.management.base import BaseCommand
from django.db.models import Case, IntegerField
from django.db.models import F
from django.db.models import Value
from django.db.models import When
from progress.bar import Bar
from scipy.io import savemat
from scipy.stats import zscore
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

import csv
from koe.aggregator import aggregators_by_type
from koe.features.feature_extract import feature_extractors, feature_map
from koe.features.feature_extract import features as full_features
from koe.models import *
from koe.models import SegmentFeature, Feature
from koe.utils import get_wav_info
from root.utils import wav_path

nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap
aggregators = aggregators_by_type['all']


# @profile
def extract_segment_features_for_audio_file(wav_file_path, segs_info, h5file, features):
    fs, length = get_wav_info(wav_file_path)
    segment_ids = [x[0] for x in segs_info]

    duration_ms = length * 1000 / fs
    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=fs, start=0, end=None,
                win_length=win_length, center=False)

    with h5py.File(h5file, 'a') as hf:
        for feature in features:
            extractor = feature_extractors[feature.name]
            existing_features = SegmentFeature.objects \
                .filter(segment__in=segment_ids, feature=feature).values_list('id', flat=True)

            for sfid in existing_features:
                sfid = str(sfid)
                if sfid in hf:
                    del hf[sfid]

            if feature.is_fixed_length:
                for seg_id, beg, end in segs_info:
                    args['start'] = beg
                    args['end'] = end
                    feature_value = extractor(args)

                    segment_feature = SegmentFeature.objects.get_or_create(feature=feature, segment_id=seg_id)[0]
                    sfid = segment_feature.id
                    hf.create_dataset(str(sfid), data=feature_value)

                    # print('Extracted feature {} for segment #{}'.format(feature.name, seg_id))

            else:
                args['start'] = 0
                args['end'] = None
                audio_file_feature_value = extractor(args)

                if feature.is_one_dimensional:
                    feature_length = max(audio_file_feature_value.shape)
                    audio_file_feature_value = audio_file_feature_value.reshape((1, feature_length))
                else:
                    feature_length = audio_file_feature_value.shape[1]

                for seg_id, beg, end in segs_info:
                    beg_idx = max(0, int(np.round(beg * feature_length / duration_ms)))
                    end_idx = min(feature_length, int(np.round(end * feature_length / duration_ms)))

                    if audio_file_feature_value.ndim == 2:
                        feature_value = audio_file_feature_value[:, beg_idx:end_idx]
                    else:
                        feature_value = audio_file_feature_value[beg_idx:end_idx]

                    segment_feature = SegmentFeature.objects.get_or_create(feature=feature, segment_id=seg_id)[0]
                    sfid = segment_feature.id
                    hf.create_dataset(str(sfid), data=feature_value)

                    # print('Extracted feature {} for segment #{}'.format(feature.name, seg_id))


def view_feature_values(h5file):
    with h5py.File(h5file, 'r') as hf:
        for key, value in hf.items():
            segment_feature_id = int(key)
            segment_feature_value = value.value

            segment_feature = SegmentFeature.objects.get(id=segment_feature_id)
            segment = segment_feature.segment
            feature = segment_feature.feature

            if feature.is_fixed_length:
                print('Segment[{}={}] of wav[{}] - feature[{}] value= [{}]'.format(
                    segment.start_time_ms, segment.end_time_ms, segment.audio_file.name,
                    feature.name, segment_feature_value
                ))
            else:
                print('Segment[{}={}] of wav[{}] - feature[{}] shape= [{}]'.format(
                    segment.start_time_ms, segment.end_time_ms, segment.audio_file.name,
                    feature.name, segment_feature_value.shape
                ))


def extract_segment_features_for_segments(sids, h5file, features):
    segments = Segment.objects.filter(id__in=sids)

    vals = segments.order_by('audio_file', 'start_time_ms') \
        .values_list('audio_file__name', 'id', 'start_time_ms', 'end_time_ms')
    af_to_segments = {}

    for name, id, start, end in vals:
        if name not in af_to_segments:
            af_to_segments[name] = []
        af_to_segments[name].append((id, start, end))

    num_audio_files = len(af_to_segments)

    bar = Bar('Extracting...', max=num_audio_files)

    for song_name, segs_info in af_to_segments.items():
        wav_file_path = wav_path(song_name)
        extract_segment_features_for_audio_file(wav_file_path, segs_info, h5file, features)
        bar.next()

    bar.finish()


def store_segment_info_in_h5(h5file):
    with h5py.File(h5file, 'r') as hf:
        info = hf.get('info', None)
        sfids = hf.keys()
        if info:
            return
        sfids = list(map(int, sfids))
        db_attrs = SegmentFeature.objects.filter(id__in=sfids). \
            values_list('id', 'segment__audio_file__name', 'segment__start_time_ms', 'segment__end_time_ms', 'feature')

        songs_info = {}
        for sfid, song_name, start, end, ft_id in db_attrs:
            if song_name not in songs_info:
                song_info = []
                songs_info[song_name] = song_info
            else:
                song_info = songs_info[song_name]
            song_info.append((start, end, ft_id, sfid))

        ft_id_to_name = {x: y for x, y in Feature.objects.values_list('id', 'name')}
        info = dict(ftmap=ft_id_to_name, songs=songs_info)

    with h5py.File(h5file, 'a') as hf:
        hf.create_dataset('info', data=json.dumps(info, indent=4))


def recalibrate_database(database_name, h5file):
    """
    If a segment feature exists in the h5 file and not in the database, import it to the database
    if it does, update the segment feature ID in the h5 file.

    :param h5file:
    :return:
    """
    temp_h5file = '/tmp/{}.h5'.format(uuid.uuid4().hex)
    with h5py.File(h5file, 'r') as hf:
        info = json.loads(hf['info'].value)
        h5_ft_id_to_name = info['ftmap']
        h5_songs_info = info['songs']
        song_names = list(h5_songs_info.keys())

        db_ft_name_to_id = {x: y for x, y in Feature.objects.values_list('name', 'id')}

        ft_h5_id_to_db_id = {}
        for id, name in h5_ft_id_to_name.items():
            if name in db_ft_name_to_id:
                ft_h5_id_to_db_id[int(id)] = db_ft_name_to_id[name]

        # Update Feature IDs in h5 file to match what's in the database
        new_h5_songs_info = {}
        for song_name, h5_info in h5_songs_info.items():
            new_h5_info = []
            for sta, end, ft_id, sfid in h5_info:
                db_ft_id = ft_h5_id_to_db_id[ft_id]
                new_h5_info.append((sta, end, db_ft_id, sfid))
            new_h5_songs_info[song_name] = new_h5_info

        h5_songs_info = new_h5_songs_info

        db_attrs = SegmentFeature.objects \
            .filter(segment__audio_file__database__name=database_name, segment__audio_file__name__in=song_names) \
            .values_list('id', 'segment__audio_file__name', 'segment__start_time_ms', 'segment__end_time_ms', 'feature')

        db_songs_info = {}
        for id, song_name, start, end, ft_id in db_attrs:
            if song_name not in db_songs_info:
                song_info = {}
                db_songs_info[song_name] = song_info
            else:
                song_info = db_songs_info[song_name]
            song_info[(start, end, ft_id)] = id

        to_add = {}
        to_update = {}
        to_keep = {}

        for song_name, h5_info in h5_songs_info.items():
            if song_name not in db_songs_info:
                to_add[song_name] = h5_info
            else:
                segments = []
                db_segment_info = db_songs_info[song_name]

                for sta, end, ft_id, sfid in h5_info:
                    key = (sta, end, ft_id)
                    if key not in db_segment_info:
                        segments.append((sta, end, ft_id, sfid))
                    else:
                        db_sfid = db_segment_info[key]
                        if db_sfid != sfid:
                            to_update[sfid] = db_sfid
                        else:
                            to_keep[sfid] = db_sfid

                if segments:
                    to_add[song_name] = segments

        if len(to_add) == 0 and len(to_update) == 0:
            print('File is consistent with database')
            return h5file

        to_update.update(to_keep)

        seg_endpoints_to_ids = {
            (sname, sta, end): sid for sid, sname, sta, end in
            Segment.objects
            .filter(audio_file__database__name=database_name, audio_file__name__in=song_names)
            .values_list('id', 'audio_file__name', 'start_time_ms', "end_time_ms")
        }

        for song_name, h5_info in to_add.items():
            for sta, end, ft_id, sfid in h5_info:
                endpoint_key = (song_name, sta, end)
                if endpoint_key in seg_endpoints_to_ids:
                    seg_id = seg_endpoints_to_ids[endpoint_key]
                    sf = SegmentFeature()
                    sf.feature_id = ft_id
                    sf.segment_id = seg_id
                    sf.save()
                    db_sfid = sf.id
                    to_update[sfid] = db_sfid

        # Update SegmentFeature IDs in h5 file to match what's in the database
        new_h5_songs_info = {}
        for song_name, h5_info in h5_songs_info.items():
            new_h5_info = []
            for sta, end, ft_id, sfid in h5_info:
                db_sfid = to_update[sfid]
                new_h5_info.append((sta, end, ft_id, db_sfid))
            new_h5_songs_info[song_name] = new_h5_info

        h5_songs_info = new_h5_songs_info

        with h5py.File(temp_h5file, 'w') as nhf:
            for h5sfid, dbsfid in to_update.items():
                data = hf[str(h5sfid)].value
                nhf.create_dataset(str(dbsfid), data=data)

            info = dict(ftmap=h5_ft_id_to_name, songs=h5_songs_info)
            nhf.create_dataset('info', data=json.dumps(info, indent=4))

        print('File seems to be exported from somewhere else. '
              'A copy that has been made consistent with the current database has been exported to ',
              temp_h5file)
        return temp_h5file


# @profile
def aggregate_feature_values(segment_to_label, h5file, features):
    """
    Compress all feature sequences into fixed-length vectors
    :param segment_to_label:
    :param h5file:
    :param features:
    :return:
    """
    if features is None or len(features) == 0:
        features = full_features

    segment_ids = segment_to_label.keys()
    feature_vectors = {}

    with h5py.File(h5file, 'r') as hf:
        segment_features = SegmentFeature.objects.filter(feature__in=features, segment__in=segment_ids) \
            .annotate(duration=F('segment__end_time_ms') - F('segment__start_time_ms')) \
            .annotate(
            n_features=Case(
                When(
                    feature__is_fixed_length=True,
                    then=Value(1)
                ),
                default=Value(len(aggregators)),
                output_field=IntegerField()
            )
        ).order_by('duration', 'feature__name')

        n_calculations = sum(list(segment_features.values_list('n_features', flat=True)))
        attrs = segment_features.values_list('id', 'feature__name', 'segment', 'duration', 'segment__audio_file__fs')

        bar = Bar('Extract features', max=n_calculations)

        for sfid, fname, sid, duration, fs in attrs:
            args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=None, start=None, end=None, win_length=win_length,
                        fs=fs, center=False)
            feature = feature_map[fname]

            if sid in feature_vectors:
                feature_vector = feature_vectors[sid]
            else:
                feature_vector = {}
                feature_vectors[sid] = feature_vector

            value = hf[str(sfid)].value

            if feature.is_fixed_length:
                feature_vector[fname] = value
                bar.next()
            else:
                if feature.is_one_dimensional:
                    value = value.reshape(1, (max(value.shape)))

                if value.ndim == 2:
                    nframes = value.shape[1]
                else:
                    nframes = value.shape[0]

                min_nsamples = nfft + (nframes - 1) * stepsize
                args['nsamples'] = min_nsamples

                for aggregator in aggregators:
                    fname_modif = '{}_{}'.format(fname, aggregator.get_name())

                    if aggregator.is_chirpy():
                        aggregated = aggregator.process(value, args=args, feature=feature)
                    else:
                        aggregated = aggregator.process(value, axis=-1)

                    if isinstance(aggregated, np.ndarray):
                        if len(aggregated) == 1:
                            feature_vector[fname_modif] = aggregated[0]
                        else:
                            for idx, x in enumerate(aggregated):
                                fname_modif_indexed = '{}_{}'.format(fname_modif, idx)
                                feature_vector[fname_modif_indexed] = x
                    else:
                        feature_vector[fname_modif] = aggregated
                    bar.next()
        bar.finish()

    assert max([len(x.values()) for x in feature_vectors.values()]) == min(
        [len(x.values()) for x in feature_vectors.values()])

    sids = []
    dataset = []
    fnames = list(next(iter(feature_vectors.values())).keys())
    fnames.sort()

    for sid, feature_vector in feature_vectors.items():
        sids.append(sid)
        feature_vector_values = [feature_vector[x] for x in fnames]
        dataset.append(feature_vector_values)

    dataset = np.array(dataset)
    return dataset, sids, fnames


def run_clustering(dataset, dim_reduce, n_components):
    if dim_reduce:
        dim_reduce_func = dim_reduce(n_components=n_components)
        dataset = dim_reduce_func.fit_transform(dataset, y=None)
        if hasattr(dim_reduce_func, 'explained_variance_ratio_'):
            print('Cumulative explained variation for {} principal components: {}'
                  .format(n_components, np.sum(dim_reduce_func.explained_variance_ratio_)))

    time_start = time.time()
    tsne = TSNE(n_components=50, verbose=1, perplexity=10, n_iter=4000)
    tsne_results = tsne.fit_transform(dataset)
    print('t-SNE done! Time elapsed: {} seconds'.format(time.time() - time_start))
    return tsne_results


def get_segment_ids_and_labels(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        supplied_fields = reader.fieldnames

        # The first field is always id, the second field is always the primary label type
        primary_label_level = supplied_fields[1]

        return {int(row['id']): row[primary_label_level] for row in reader}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--database-name',
            action='store',
            dest='database_name',
            required=True,
            type=str,
            help='E.g Bellbird, Whale, ..., case insensitive',
        )

        parser.add_argument(
            '--csv',
            action='store',
            dest='segment_csv',
            required=True,
            type=str,
            help='CSV file containing IDs + labels of the segments to be extracted',
        )

        parser.add_argument(
            '--h5file',
            action='store',
            dest='h5file',
            required=True,
            type=str,
            help='Name of the h5 file to store extracted feature values',
        )

        parser.add_argument(
            '--matfile',
            action='store',
            dest='matfile',
            required=False,
            type=str,
            help='Name of the .mat file to store extracted feature values for Matlab',
        )

        parser.add_argument(
            '--features',
            action='store',
            dest='selected_features',
            required=False,
            type=str,
            help='List of features to be extracted',
        )

    def handle(self, *args, **options):
        selected_features = options['selected_features'].split(';')
        matfile = options['matfile']
        h5file = options['h5file']
        segment_csv = options['segment_csv']
        database_name = options['database_name']

        sid_to_label = get_segment_ids_and_labels(segment_csv)
        sids = sid_to_label.keys()

        selected_features = list(Feature.objects.filter(name__in=selected_features))

        if not os.path.isfile(h5file):
            try:
                extract_segment_features_for_segments(sids, h5file, full_features)
                store_segment_info_in_h5(h5file)
            except Exception as e:
                os.remove(h5file)
                raise e
        else:
            h5file = recalibrate_database(database_name, h5file)

        rawdata, sids, fnames = aggregate_feature_values(sid_to_label, h5file, selected_features)

        sids = np.array(sids, dtype=np.int32)
        labels = []
        for sid in sids:
            label = sid_to_label[sid]
            labels.append(label)

        clusters = run_clustering(zscore(rawdata, axis=1), dim_reduce=PCA, n_components=50)

        labels = np.array(labels)
        label_sort_ind = np.argsort(labels)
        labels = labels[label_sort_ind]
        sids = sids[label_sort_ind]
        rawdata = rawdata[label_sort_ind, :]
        clusters = clusters[label_sort_ind, :]

        savemat(matfile, dict(sids=sids, rawdata=rawdata, labels=labels, fnames=fnames, clusters=clusters))
