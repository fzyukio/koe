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

from koe.ml.nd_vl_s2s_autoencoder import NDS2SAEFactory
from koe.model_utils import get_or_error
from koe.models import Database, Segment
from koe.spect_utils import extractors
from koe.utils import wav_path
from root.utils import mkdirp


def read_variables(save_to):
    with zipfile.ZipFile(save_to, 'r', zipfile.ZIP_BZIP2, False) as zip_file:
        content = zip_file.read('variables')
        content = str(content, "utf-8")
        variables = json.loads(content)
    return variables


def extract_syllables(database_name, spect_dir, format):
    database = get_or_error(Database, dict(name__iexact=database_name))
    segments = Segment.objects.filter(audio_file__database=database)

    extractor = extractors[format]

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
            spect_name = '{}.{}'.format(sid, format)
            spect_path = os.path.join(spect_dir, spect_name)

            if not os.path.isfile(spect_path):
                extractor(wav_file_path, fs, start, end, spect_path)

            bar.next()
    bar.finish()


def read_spect_dir(spect_dir, format):
    variables = dict(current_batch_index=dict(train=0, test=0), dims=None, spect_dir=spect_dir)
    sids = []
    ext_length = len(format) + 1
    for filename in os.listdir(spect_dir):
        if filename.lower().endswith('.{}'.format(format)):
            sid = int(filename[:-ext_length])
            sids.append(sid)
            spect_path = os.path.join(spect_dir, filename)
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                dims, length = spect.shape

                if variables['dims'] is None:
                    variables['dims'] = dims
    variables['sids'] = sids
    return variables


def create_training_set(variables, save_to):
    sids = variables['sids']
    n_samples = len(sids)
    n_train = n_samples * 9 // 10
    n_test = n_samples - n_train
    np.random.shuffle(sids)

    sids_for_training = sids[:n_train]
    sids_for_testing = sids[n_train:]

    variables['sids_for_training'] = sids_for_training
    variables['sids_for_testing'] = sids_for_testing
    variables['n_train'] = n_train
    variables['n_test'] = n_test

    content = json.dumps(variables)
    with zipfile.ZipFile(save_to, 'w', zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr('variables', content)


def train(variables, save_to):
    sids_for_training = variables['sids_for_training']
    sids_for_testing = variables['sids_for_testing']
    n_train = len(sids_for_training)
    n_test = len(sids_for_testing)
    spect_dir = variables['spect_dir']
    format = variables['format']
    topology = variables['topology']
    batch_size = variables['batch_size']
    n_iterations = variables['n_iterations']

    batch_index_limits = dict(train=n_train, test=n_test)
    sids_collections = dict(train=sids_for_training, test=sids_for_testing)

    def get_batch(this_batch_size=10, data_type='train'):
        batch_index_limit = batch_index_limits[data_type]
        sids_collection = sids_collections[data_type]
        if this_batch_size is None:
            this_batch_size = batch_index_limit

        current_batch_index = variables['current_batch_index'][data_type]
        next_batch_index = current_batch_index + this_batch_size

        if current_batch_index == 0:
            np.random.shuffle(sids_collection)

        if next_batch_index >= batch_index_limit:
            next_batch_index = batch_index_limit
            variables['current_batch_index'][data_type] = 0
            final_batch = True
        else:
            variables['current_batch_index'][data_type] = next_batch_index
            final_batch = False

        batch_ids = sids_for_training[current_batch_index:next_batch_index]

        spects = []

        for i, sid in enumerate(batch_ids):
            spect_path = os.path.join(spect_dir, '{}.{}'.format(sid, format))
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                spects.append(spect.transpose(1, 0))

        return spects, spects, final_batch

    def train_batch_gen(batch_size):
        return get_batch(batch_size, 'train')

    def test_batch_gen(batch_size):
        return get_batch(batch_size, 'test')

    factory = NDS2SAEFactory()
    if os.path.isfile(save_to):
        factory.load(save_to)
    factory.lrtype = variables['lrtype']
    factory.lrargs = variables['lrargs']
    factory.input_dim = variables['dims']
    factory.output_dim = variables['dims']
    factory.keep_prob = None
    factory.stop_pad_length = 5
    factory.stop_pad_token = 0
    factory.pad_token = -2
    factory.go_token = -3
    factory.layer_sizes = infer_topology(topology, variables['dims'])
    encoder = factory.build(save_to)
    encoder.train(train_batch_gen, test_batch_gen, batch_size=batch_size, n_iterations=n_iterations, display_step=100,
                  save_step=200)


def infer_topology(topology, dims=None):
    layer_sizes = []
    if dims is None:
        try:
            topology = list(topology.split(','))
            for number in topology:
                try:
                    number = int(number)
                except ValueError:
                    number = float(number)
                layer_sizes.append(number)
        except ValueError:
            raise Exception('Network topology must be either a single number or a list of comma separated numbers')
    else:
        layer_sizes = []
        for number in topology:
            if isinstance(number, int):
                layer_sizes.append(number)
            else:
                layer_sizes.append(int(number * dims))
    return layer_sizes


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=False, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--spect-dir', action='store', dest='spect_dir', required=True, type=str,
                            help='Path to the directory where audio segments reside', )
        parser.add_argument('--format', action='store', dest='format', required=True, type=str)
        parser.add_argument('--save-to', action='store', dest='save_to', required=True, type=str)
        parser.add_argument('--batch-size', action='store', dest='batch_size', required=True, type=int)
        parser.add_argument('--n-iterations', action='store', dest='n_iterations', required=True, type=int)
        parser.add_argument('--lrtype', action='store', dest='lrtype', default='constant', type=str)
        parser.add_argument('--lrargs', action='store', dest='lrargs', default='{"lr": 0.001}', type=str)
        parser.add_argument('--topology', action='store', dest='topology', default='1', type=str,
                            help='Network topology of the encoder, can be a single number or comma-separated list.'
                                 'A float (e.g. 0.5, 1.5) corresponds to the ratio of number of neurons to input size'
                                 'An integer (e.g. 1, 2, 200) corresponds to the number of neurons.'
                                 'E.g. "0.5, 100" means 2 layers, the first layer has 0.5xinput size neurons, '
                                 'the second layer has 100 neurons. The final encoded representation has dimension '
                                 'equals to the total number of neurons in all layers.'
                            )

    def handle(self, *args, **options):
        database_name = options['database_name']
        spect_dir = options['spect_dir']
        save_to = options['save_to']
        format = options['format']
        batch_size = options['batch_size']
        n_iterations = options['n_iterations']
        lrtype = options['lrtype']
        lrargs = json.loads(options['lrargs'])
        topology = infer_topology(options['topology'])

        if not save_to.lower().endswith('.zip'):
            save_to += '.zip'

        if database_name is not None:
            if os.path.isdir(spect_dir):
                warning('{} already exists as a folder. It\'s better to extract to a new folder'.format(spect_dir))
            else:
                mkdirp(spect_dir)
            extract_syllables(database_name, spect_dir, format)

        if os.path.isfile(save_to):
            info('===========CONTINUING===========')
            variables = read_variables(save_to)
        else:
            variables = read_spect_dir(spect_dir, format)
            create_training_set(variables, save_to)
        variables['format'] = format
        variables['topology'] = topology
        variables['batch_size'] = batch_size
        variables['n_iterations'] = n_iterations
        variables['lrtype'] = lrtype
        variables['lrargs'] = lrargs
        train(variables, save_to)
