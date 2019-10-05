"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import json
import os
import pickle
import random
import zipfile
from logging import warning, info
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from progress.bar import Bar
from scipy.ndimage.interpolation import zoom

from koe.ml.nd_vl_s2s import NDS2SFactory
from koe.models import AudioFile
from koe.models import Segment
from koe.spect_utils import extractors, psd2img, binary_img
from koe.utils import split_segments
from koe.utils import wav_path
from koe.wavfile import read_wav_info
from root.utils import mkdirp


def read_variables(save_to):
    with zipfile.ZipFile(save_to, 'r', zipfile.ZIP_BZIP2, False) as zip_file:
        content = zip_file.read('variables')
        content = str(content, "utf-8")
        variables = json.loads(content)
    return variables


def extract_psd(extractor, audio_file, normalise=True):
    """
    Extract audio file's spectrogram given its ID
    :param audio_file:
    :param extractor:
    :return: the normalised spectrogram (spectrogram - wise, not dimension wise)
    """
    wav_file_path = wav_path(audio_file)
    spect = extractor(wav_file_path, audio_file.fs, 0, None)
    spect_min = np.min(spect)

    if normalise:
        spect_max = np.max(spect)

        return (spect - spect_min) / (spect_max - spect_min)
    else:
        return spect


def create_segment_profile(audio_file, duration_frames, filepath, window_len, step_size=1):
    """
    Each audio file has a number of segments. We'll slide a window through it spectrogam to create segments.
    then we create a mask for each segment with the same length corresponding to the frame number of the segment.
    For each frame of the segments that falls into the boundary of a syllable, its corresponding value in the mask
     is 1, otherwise 0.
    Each of these windowed segments is given a unique ID that is constructible from the audio file's ID and the
     timestamp
    :param step_size: how many frames is the next segment ahead of the
    :param window_len: length of the sliding window
    :param audio_file:
    :return: a dictionary of (fake) segment IDs and their corresponding audiofile, start and end indices
    """
    noverlap = window_len - step_size
    real_segments = Segment.objects.filter(audio_file=audio_file)
    real_segments_timestamps = real_segments.values_list('start_time_ms', 'end_time_ms')

    # Construct a mask for the entire audiofile, then simply slicing it into fake segments
    duration_ms = int(audio_file.length / audio_file.fs * 1000)

    mask = np.zeros((duration_frames, 1), dtype=np.float32)
    for beg, end in real_segments_timestamps:
        beg_frame = int(beg / duration_ms * duration_frames)
        end_frame = int(end / duration_ms * duration_frames)
        mask[beg_frame:end_frame, :] = 1

    nwindows, windows = split_segments(duration_frames, window_len, noverlap, incltail=False)
    profiles = {}
    for beg, end in windows:
        windowed_id = '{}_{}'.format(audio_file.id, beg)
        windowed_mask = mask[beg:end, :].tolist()
        profiles[windowed_id] = (filepath, beg, end, windowed_mask)

    return profiles


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
    keep_prob = variables['keep_prob']
    f0_dir = variables['f0_dir']

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
        f0s = []

        for i, seg_id in enumerate(batch_ids):
            spect_path = os.path.join(spect_dir, '{}.{}'.format(seg_id, format))
            f0_path = os.path.join(f0_dir, '{}.{}'.format(seg_id, 'pkl'))

            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                spects.append(spect.transpose(1, 0))
                h_spect, w_spect = spect.shape
                is_log_psd = False
                origi_path = '/tmp/'+seg_id+"_spect.png"
                psd2img(spect, origi_path, is_log_psd)

            with open(f0_path, 'rb') as f:
                f0 = pickle.load(f)['binary']
                h_f0, w_f0 = f0.shape
                f0 = f0.astype(float)

                # binary_img(f0, '/tmp/blah-original.png')
                f0 = zoom(f0, ((h_spect * 1.0)/h_f0, (w_spect * 1.0) / w_f0))
                # binary_img(f0, '/tmp/blah-zoomed.png')
                f0 = (f0 > 0.5).astype(np.float)
                origi_path = '/tmp/' + seg_id + "_f0.png"
                binary_img(f0, origi_path)

                f0s.append(f0.transpose(1, 0))

        return spects, f0s, final_batch

    def train_batch_gen(batch_size):
        return get_batch(batch_size, 'train')

    def test_batch_gen(batch_size):
        return get_batch(batch_size, 'test')

    factory = NDS2SFactory()
    if os.path.isfile(save_to):
        factory.set_output(save_to)
    factory.lrtype = variables['lrtype']
    factory.lrargs = variables['lrargs']
    factory.input_dim = variables['dims']
    factory.output_dim = variables['dims']
    factory.keep_prob = keep_prob
    factory.stop_pad_length = 5
    factory.stop_pad_token = 0
    factory.pad_token = -2
    factory.go_token = -3
    factory.layer_sizes = infer_topology(topology, variables['dims'])
    encoder = factory.build()
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


def extract_specs(wav_dir, tsv_file, spect_dir, format):
    extractor = extractors[format]
    csv_file_content = pd.read_csv(tsv_file, sep='\t')

    csv_lines = [x for x in csv_file_content.values]
    bar = Bar('Exporting segments ...', max=len(csv_lines))
    for seg_id, filename, seg_start, seg_end in csv_lines:
        spect_path = Path(spect_dir, '{}.{}'.format(seg_id, format))
        if not os.path.isfile(spect_path):
            wav_file_path = Path(wav_dir, filename)
            fs = read_wav_info(wav_file_path)
            extractor(wav_file_path, fs, seg_start, seg_end, spect_path)
        bar.next()

    bar.finish()


def read_spect_dir(spect_dir, format):
    variables = dict(current_batch_index=dict(train=0, test=0), dims=None, spect_dir=spect_dir)
    sids = []
    ext_length = len(format) + 1
    for filename in os.listdir(spect_dir):
        if filename.lower().endswith('.{}'.format(format)):
            # sid = int(filename[:-ext_length])
            sid = filename[:-ext_length]
            sids.append(sid)
            spect_path = os.path.join(spect_dir, filename)
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                dims, length = spect.shape

                if variables['dims'] is None:
                    variables['dims'] = dims

    random.shuffle(sids)
    variables['sids_train'] = sids[:10000]
    variables['sids_test'] = sids[10000:]
    return variables


def create_training_set(variables, save_to):
    sids = variables['sids_train']
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


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--wav-dir', action='store', dest='wav_dir', required=False, type=str,
                            help='Path to the directory where wav files reside')
        parser.add_argument('--tsv-file', action='store', dest='tsv_file', required=True, type=str,
                            help='Path to tsv file')
        parser.add_argument('--spect-dir', action='store', dest='spect_dir', required=True, type=str,
                            help='Target path to store the spect features')
        parser.add_argument('--f0-dir', action='store', dest='f0_dir', required=True, type=str,
                            help='Target path to store the spect features')
        parser.add_argument('--format', action='store', dest='format', required=True, type=str)
        parser.add_argument('--save-to', action='store', dest='save_to', required=True, type=str)
        parser.add_argument('--batch-size', action='store', dest='batch_size', required=True, type=int)
        parser.add_argument('--n-iterations', action='store', dest='n_iterations', required=True, type=int)
        parser.add_argument('--lrtype', action='store', dest='lrtype', default='constant', type=str)
        parser.add_argument('--lrargs', action='store', dest='lrargs', default='{"lr": 0.001}', type=str)
        parser.add_argument('--keep-prob', action='store', dest='keep_prob', default=None, type=float)
        parser.add_argument('--topology', action='store', dest='topology', default='1', type=str,
                            help='Network topology of the encoder, can be a single number or comma-separated list.'
                                 'A float (e.g. 0.5, 1.5) corresponds to the ratio of number of neurons to input size'
                                 'An integer (e.g. 1, 2, 200) corresponds to the number of neurons.'
                                 'E.g. "0.5, 100" means 2 layers, the first layer has 0.5xinput size neurons, '
                                 'the second layer has 100 neurons. The final encoded representation has dimension '
                                 'equals to the total number of neurons in all layers.'
                            )

    def handle(self, *args, **options):
        wav_dir = options['wav_dir']
        tsv_file = options['tsv_file']
        spect_dir = options['spect_dir']
        f0_dir = options['f0_dir']
        save_to = options['save_to']
        format = options['format']
        batch_size = options['batch_size']
        n_iterations = options['n_iterations']
        lrtype = options['lrtype']
        lrargs = json.loads(options['lrargs'])
        keep_prob = options['keep_prob']
        topology = infer_topology(options['topology'])

        if not save_to.lower().endswith('.zip'):
            save_to += '.zip'

        if os.path.isdir(spect_dir):
            warning('{} already exists as a folder. It\'s better to extract to a new folder'.format(spect_dir))
        else:
            mkdirp(spect_dir)
            extract_specs(wav_dir, tsv_file, spect_dir, format)

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
        variables['keep_prob'] = keep_prob
        variables['f0_dir'] = f0_dir

        train(variables, save_to)


