import os
import h5py
import numpy as np
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.features.feature_extract import feature_extractors
from koe.features.feature_extract import features as full_features
from koe.models import *
from koe.models import SegmentFeature, Feature
from root.models import ExtraAttr, ExtraAttrValue, ValueTypes
from root.utils import wav_path


def extract_segment_features_for_audio_file(audio_file, h5file, features):
    nfft = 512
    noverlap = nfft * 3 // 4
    win_length = nfft

    # print('Extracting segment features of {}'.format(audio_file.name))

    duration_ms = audio_file.length * 1000 / audio_file.fs
    all_segments = Segment.objects.filter(audio_file=audio_file)
    segment_endpoints = list(all_segments.values_list('id', 'start_time_ms', 'end_time_ms'))

    wav_file_path = wav_path(audio_file.name)
    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=audio_file.fs, start=0, end=None,
                win_length=win_length)

    with h5py.File(h5file, 'a') as hf:
        for feature in features:
            extractor = feature_extractors[feature]
            existing_features = SegmentFeature.objects.filter(segment__in=all_segments, feature=feature).values_list(
                'id', flat=True)
            for sfid in existing_features:
                sfid = str(sfid)
                if sfid in hf:
                    del hf[sfid]

            if feature.is_fixed_length:
                for seg_id, beg, end in segment_endpoints:
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

                for seg_id, beg, end in segment_endpoints:
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


def extract_segment_features_for_audio_files(audio_files, h5file, features):
    bar = Bar('Extracting...', max=audio_files.count())

    for audio_file in audio_files:
        extract_segment_features_for_audio_file(audio_file, h5file, features)
        bar.next()

    bar.finish()


def create_dataset(audio_files, h5file, matfile, features):
    segments = Segment.objects.filter(audio_file__in=audio_files)
    feature_vectors = {}
    aggregators = [np.mean, np.median, np.std]

    with h5py.File(h5file, 'r') as hf:
        for feature in features:
            segment_features = SegmentFeature.objects.filter(feature=feature, segment__in=segments) \
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

    label_attr, _ = ExtraAttr.objects.get_or_create(klass=Segment.__name__, name='label', type=ValueTypes.SHORT_TEXT)
    segment_labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=sids).values_list('owner_id', 'value')
    segment_labels = {x: y for x, y in segment_labels}

    labels = []
    for sid in sids:
        label = segment_labels.get(sid, '__NONE__')
        labels.append(label)

    dataset = np.array(dataset)
    sids = np.array(sids, dtype=np.int32)

    from scipy.io import savemat
    savemat(matfile, dict(sids=sids, dataset=dataset, labels=labels))


class Command(BaseCommand):
    def handle(self, *args, **options):
        audio_files = AudioFile.objects.filter(database__name__iexact='BirdCLEF')
        h5file = 'birdclef.h5'
        matfile = '/tmp/mt-birdclef.mat'

        selected_features = list(Feature.objects.filter(name__in=[
            'frequency_modulation', 'amplitude_modulation', 'goodness_of_pitch', 'spectral_continuity',
            'mean_frequency', 'entropy', 'amplitude', 'duration'
        ]))

        if not os.path.isfile(h5file):
            extract_segment_features_for_audio_files(audio_files, h5file, full_features)
        create_dataset(audio_files, h5file, matfile, selected_features)
