r"""
Run this to generate a CSV file that has two columns: id and label.
ID=ids of the segments, label=Label given to that segment

e.g:

- python manage.py segment_select --database-name=bellbirds --owner=superuser --csv-file=/tmp/bellbirds.csv \
                                  --startswith=LBI --label-level=label_family --labels-to-ignore="Click;Stutter"
  --> Find segments of Bellbirds database, where the files start with LBI and family labels made by superuser, ignore
      all segments that are labelled 'Click' or 'Stutter', save to file /tmp/bellbirds.csv
"""
import os
import pickle

import numpy as np
import pydub
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe import wavfile
from koe.features.scaled_freq_features import mfcc
from koe.features.utils import get_spectrogram
from koe.model_utils import exclude_no_labels, get_or_error, select_instances
from koe.model_utils import get_labels_by_sids
from koe.models import *
from koe.utils import wav_path, get_kfold_indices
from root.models import User
from root.utils import ensure_parent_folder_exists

nfft = 512
noverlap = nfft // 2
win_length = nfft
stepsize = nfft - noverlap


def extract_spect(wav_file_path, fs, start, end, spect_path):
    psd = get_spectrogram(wav_file_path, fs=fs, start=start, end=end, nfft=nfft, noverlap=noverlap, win_length=nfft,
                          center=False)
    with open(spect_path, 'wb') as f:
        pickle.dump(psd, f)


def extract_mfcc(wav_file_path, fs, start, end, filepath):
    sig = wavfile.read_segment(wav_file_path, beg_ms=start, end_ms=end, mono=True)
    args = dict(nfft=nfft, noverlap=noverlap, win_length=win_length, fs=fs, wav_file_path=None, start=0, end=None,
                sig=sig, center=True)
    mfcc_value = mfcc(args)
    with open(filepath, 'wb') as f:
        pickle.dump(mfcc_value, f)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--annotator', action='store', dest='annotator_name', default='superuser', type=str,
                            help='Name of the person who labels this dataset, case insensitive', )

        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )

        parser.add_argument('--min-occur', action='store', dest='min_occur', default=2, type=int,
                            help='Ignore syllable classes that have less than this number of instances', )

        parser.add_argument('--num-instances', action='store', dest='num_instances', default=None, type=int,
                            help='Number of instances per class to extract. Must be >= min_occur', )

        parser.add_argument('--save-to', action='store', dest='save_to', required=True, type=str, )

        parser.add_argument('--format', action='store', dest='format', default='wav', type=str, )

    def handle(self, *args, **options):
        database_name = options['database_name']
        annotator_name = options['annotator_name']
        label_level = options['label_level']
        save_to = options['save_to']
        format = options['format']
        min_occur = options['min_occur']
        num_instances = options['num_instances']

        if num_instances is not None:
            assert num_instances >= min_occur, 'num_instances must be >= min_occur'

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        segments = Segment.objects.filter(audio_file__database=database)

        sids = np.array(list(segments.order_by('id').values_list('id', flat=True)))

        labels, no_label_ids = get_labels_by_sids(sids, label_level, annotator, min_occur)
        if len(no_label_ids) > 0:
            sids, _, labels = exclude_no_labels(sids, None, labels, no_label_ids)

        if num_instances:
            sids, _, labels = select_instances(sids, None, labels, num_instances)

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        fold_indices = get_kfold_indices(enum_labels, 10)

        segments_info = {sid: (label, label_enum, fold_ind) for sid, label, label_enum, fold_ind
            in zip(sids, labels, enum_labels, fold_indices)}

        segs = Segment.objects.filter(id__in=sids)

        audio_file_dict = {}
        for seg in segs:
            af = seg.audio_file
            if af in audio_file_dict:
                info = audio_file_dict[af]
            else:
                info = []
                audio_file_dict[af] = info
            info.append((seg.id, seg.start_time_ms, seg.end_time_ms))

        audio_info = []

        bar = Bar('Exporting segments ...', max=len(segs))
        metadata_file_path = os.path.join(save_to, 'metadata.tsv')

        for af, info in audio_file_dict.items():
            wav_file_path = wav_path(af)
            fullwav = pydub.AudioSegment.from_wav(wav_file_path)

            for id, start, end in info:
                label, label_enum, fold_ind = segments_info[id]

                audio_segment = fullwav[start: end]

                filename = '{}.{}'.format(id, format)

                filepath = os.path.join(save_to, filename)
                ensure_parent_folder_exists(filepath)

                if format == 'spect':
                    if not os.path.isfile(filepath):
                        extract_spect(wav_file_path, af.fs, start, end, filepath)
                elif format == 'mfcc':
                    if not os.path.isfile(filepath):
                        extract_mfcc(wav_file_path, af.fs, start, end, filepath)
                else:
                    with open(filepath, 'wb') as f:
                        audio_segment.export(f, format=format)

                audio_info.append(
                    (id, filename, label, label_enum, fold_ind)
                )

                bar.next()

        with open(metadata_file_path, 'w') as f:
            f.write('id\tfilename\tlabel\tlabel_enum\tfold\n')
            for id, filename, label, label_enum, fold_ind in audio_info:
                f.write('{}\t{}\t{}\t{}\t{}\n'.format(id, filename, label, label_enum, fold_ind))

        bar.finish()
