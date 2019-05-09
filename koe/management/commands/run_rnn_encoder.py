"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import json
import os
import pickle
import zipfile
from logging import warning, info

import numpy as np

from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.features.utils import get_spectrogram
from koe.ml.variable_length_s2s_autoencoder import VLS2SAutoEncoderFactory
from koe.model_utils import get_or_error
from koe.models import Database, Segment
from koe.utils import wav_path
from root.utils import mkdirp

nfft = 512
noverlap = nfft // 2
win_length = nfft
stepsize = nfft - noverlap


def extract_spect(wav_file_path, fs, start, end, spect_path):
    psd = get_spectrogram(wav_file_path, fs=fs, start=start, end=end, nfft=nfft, noverlap=noverlap, win_length=nfft,
                          center=False)
    with open(spect_path, 'wb') as f:
        pickle.dump(psd, f)


def extract_syllables(database_name, spect_dir):
    database = get_or_error(Database, dict(name__iexact=database_name))
    segments = Segment.objects.filter(audio_file__database=database)

    audio_file_dict = {}
    for seg in segments:
        af = seg.audio_file
        if af in audio_file_dict:
            info = audio_file_dict[af]
        else:
            info = []
            audio_file_dict[af] = info
        info.append((seg.id, seg.start_time_ms, seg.end_time_ms))

    bar = Bar('Exporting segments ...', max=len(segments))

    for af, info in audio_file_dict.items():
        wav_file_path = wav_path(af)
        fs = af.fs

        for sid, start, end in info:
            spect_name = '{}.spect'.format(sid)
            spect_path = os.path.join(spect_dir, spect_name)
            if not os.path.isfile(spect_path):
                extract_spect(wav_file_path, fs, start, end, spect_path)

            bar.next()
    bar.finish()


def read_spect_dir(spect_dir):
    ii32 = np.iinfo(np.int32)
    variables = dict(current_batch_index=0, min_length=ii32.max, max_length=ii32.min, dims=None,
                     spect_dir=spect_dir)
    sids = []
    for filename in os.listdir(spect_dir):
        if filename.lower().endswith('.spect'):
            sid = int(filename[:-6])
            sids.append(sid)
            spect_path = os.path.join(spect_dir, filename)
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                dims, length = spect.shape

                if variables['dims'] is None:
                    variables['dims'] = dims
                variables['min_length'] = min(variables['min_length'], length)
                variables['max_length'] = max(variables['max_length'], length)
    variables['sids'] = sids
    return variables


def create_training_set(variables, save_to):
    sids = variables['sids']
    n_samples = len(sids)
    n_train = n_samples * 9 // 10
    np.random.shuffle(sids)

    sids_for_training = sids[:n_train]
    sids_for_testing = sids[n_train:]

    variables['sids_for_training'] = sids_for_training
    variables['sids_for_testing'] = sids_for_testing
    variables['n_train'] = n_train

    content = json.dumps(variables)
    with zipfile.ZipFile(save_to, 'w', zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr('variables', content)


def train(variables, save_to):
    sids_for_training = variables['sids_for_training']
    n_train = variables['n_train']
    spect_dir = variables['spect_dir']
    batch_size = 50

    def get_batch(batch_size=10):
        current_batch_index = variables['current_batch_index']
        next_batch_index = current_batch_index + batch_size
        if next_batch_index > n_train:
            np.random.shuffle(sids_for_training)
            current_batch_index = 0
            next_batch_index = batch_size

            # content = json.dumps(variables)
            # with zipfile.ZipFile(save_to, 'a', zipfile.ZIP_BZIP2, False) as zip_file:
            #     zip_file.writestr('variables', content)

        batch_ids = sids_for_training[current_batch_index:next_batch_index]
        variables['current_batch_index'] = next_batch_index

        spects = []
        lengths = []

        mask = np.zeros((batch_size, variables['max_length']), dtype=np.float32)

        for i, sid in enumerate(batch_ids):
            spect_path = os.path.join(spect_dir, '{}.spect'.format(sid))
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                dims, length = spect.shape
                spect_padded = np.zeros((dims, variables['max_length']), dtype=spect.dtype)
                spect_padded[:, :length] = spect
                spects.append(spect_padded)
                lengths.append(length)
                mask[i, :length] = 1

        sequences = np.array(spects).transpose(0, 2, 1)
        return sequences, lengths, mask

    factory = VLS2SAutoEncoderFactory()
    factory.max_seq_len = variables['max_length']
    factory.min_seq_len = variables['min_length']
    factory.n_inputs = variables['dims']
    factory.n_outputs = variables['dims']
    factory.encode_layer_sizes = [variables['dims'] * 2, variables['dims']]
    factory.decode_layer_sizes = [variables['dims'], variables['dims'] * 2]
    factory.kernel_size = variables['dims'] // 2
    encoder = factory.build(save_to)
    encoder.train(get_batch, batch_size=batch_size, n_iterations=3000)


def read_variables(save_to):
    with zipfile.ZipFile(save_to, 'r', zipfile.ZIP_BZIP2, False) as zip_file:
        variables = json.loads(zip_file.read('variables'))
    return variables


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--spect-dir', action='store', dest='spect_dir', required=True, type=str,
                            help='Path to the directory where audio segments reside', )
        parser.add_argument('--save-to', action='store', dest='save_to', required=True, type=str,
                            help='Path to the directory where audio segments reside', )

    def handle(self, *args, **options):
        database_name = options['database_name']
        spect_dir = options['spect_dir']
        save_to = options['save_to']
        if not save_to.lower().endswith('.zip'):
            save_to += '.zip'

        if os.path.isdir(spect_dir):
            warning('{} already exists as a folder. It\'s better to extract to a new folder'.format(spect_dir))
        else:
            mkdirp(spect_dir)
        extract_syllables(database_name, spect_dir)

        if os.path.isfile(save_to):
            info('===========CONTINUING===========')
            variables = read_variables(save_to)
        else:
            variables = read_spect_dir(spect_dir)
            create_training_set(variables, save_to)
        train(variables, save_to)
