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
import csv
import os

import h5py
import numpy as np
import time
from django.core.management.base import BaseCommand
from progress.bar import Bar
from scipy.stats import zscore

from koe.features.feature_extract import feature_extractors
from koe.features.feature_extract import features as full_features
from koe.models import *
from koe.models import SegmentFeature, Feature
from koe.utils import get_wav_info
from root.utils import wav_path

from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from scipy.io import savemat


def extract_segment_features_for_audio_file(wav_file_path, segs_info, h5file, features):
    nfft = 512
    noverlap = nfft * 3 // 4
    win_length = nfft

    fs, length = get_wav_info(wav_file_path)
    segment_ids = [x[0] for x in segs_info]

    duration_ms = length * 1000 / fs
    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=fs, start=0, end=None,
                win_length=win_length)

    with h5py.File(h5file, 'a') as hf:
        for feature in features:
            extractor = feature_extractors[feature]
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
                    audio_file_feature_value = audio_file_feature_value.reshape((max(audio_file_feature_value.shape),))
                    feature_length = audio_file_feature_value.shape[0]
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


def create_dataset(segment_to_label, h5file, features):
    if features is None or len(features) == 0:
        features = full_features

    segment_ids = segment_to_label.keys()
    feature_vectors = {}
    aggregators = [np.mean, np.median, np.std]

    with h5py.File(h5file, 'r') as hf:
        for feature in features:
            segment_features = SegmentFeature.objects.filter(feature=feature, segment__in=segment_ids) \
                .values_list('id', 'segment')

            for sfid, sid in segment_features:
                if sid in feature_vectors:
                    feature_vector = feature_vectors[sid]
                else:
                    feature_vector = []
                    feature_vectors[sid] = feature_vector

                value = hf[str(sfid)].value

                if feature.is_fixed_length:
                    feature_vector.append(value)
                else:
                    for aggregator in aggregators:
                        aggregated = aggregator(value, axis=-1)
                        if isinstance(aggregated, np.ndarray):
                            if len(aggregated) == 1:
                                feature_vector.append(aggregated[0])
                            else:
                                for x in aggregated:
                                    feature_vector.append(x)
                        else:
                            feature_vector.append(aggregated)

    assert max([len(x) for x in feature_vectors.values()]) == min([len(x) for x in feature_vectors.values()])

    sids = []
    dataset = []

    for sid, feature_vector in feature_vectors.items():
        sids.append(sid)
        dataset.append(feature_vector)

    dataset = np.array(dataset)
    return dataset, sids


def run_clustering(dataset):
    ndim = dataset.shape[1]
    n_components = min(50, ndim // 2)
    pca = PCA(n_components=n_components)
    pca_result = pca.fit_transform(dataset)
    print('Cumulative explained variation for {} principal components: {}'
          .format(n_components, np.sum(pca.explained_variance_ratio_)))

    time_start = time.time()
    tsne = TSNE(n_components=3, verbose=1, perplexity=10, n_iter=4000)
    tsne_pca_results = tsne.fit_transform(pca_result)
    print('t-SNE done! Time elapsed: {} seconds'.format(time.time() - time_start))
    return tsne_pca_results


class Command(BaseCommand):
    def add_arguments(self, parser):
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

        with open(segment_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')

            supplied_fields = reader.fieldnames
            required_fields = ['id', 'label']
            missing_fields = [x for x in required_fields if x not in supplied_fields]

            if missing_fields:
                raise ValueError('Field(s) {} are required but not found in your CSV file'
                                 .format(','.join(missing_fields)))

            sid_to_label = {int(row['id']): row['label'] for row in reader}

        sids = sid_to_label.keys()

        selected_features = list(Feature.objects.filter(name__in=selected_features))

        if not os.path.isfile(h5file):
            try:
                extract_segment_features_for_segments(sids, h5file, full_features)
            except Exception as e:
                os.remove(h5file)
                raise e

        dataset, sids = create_dataset(sid_to_label, h5file, selected_features)
        dataset = zscore(dataset)
        sids = np.array(sids, dtype=np.int32)
        labels = []
        for sid in sids:
            label = sid_to_label.get(sid, '__NONE__')
            labels.append(label)

        clusters = run_clustering(dataset)

        labels = np.array(labels)
        label_sort_ind = np.argsort(labels)
        labels = labels[label_sort_ind]
        sids = sids[label_sort_ind]
        dataset = dataset[label_sort_ind, :]
        clusters = clusters[label_sort_ind, :]
        sids = sids[label_sort_ind]

        savemat(matfile, dict(sids=sids, dataset=dataset, labels=labels, clusters=clusters))
