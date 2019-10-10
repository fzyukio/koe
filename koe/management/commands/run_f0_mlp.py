"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import pandas as pd
import json
import os
import pickle
import zipfile
from logging import info

import numpy as np
from django.core.management.base import BaseCommand
from scipy.ndimage.interpolation import zoom

from koe.ml.nd_mlp import NDMLPFactory
from koe.models import Segment
from koe.spect_utils import extractors
from koe.utils import split_segments, get_wav_info
from koe.utils import wav_path
from root.utils import mkdirp

good_audio_file_name = [
    'LAI_2015_05_28_DHB018_01_F.G.LAI_2015_05_28_DHB016Aposs.Downs.wav',
    'LAI_2015_05_28_DHB031_01_F.EX.LAI_2015_05_28_DHB031A..wav',
    'LAI_2015_05_28_MMR001_01_M.EX.LAI_2015_05_28_MMR001A.2SylsCh2.wav',
    'LAI_2015_05_29_BAE028_01_M.VG..wav',
    'LAI_2015_05_29_WHW002_05_FU.G.wav',
    'LAI_2015_05_29_WHW004_04_U.G...wav',
    'LAI_2015_05_30_DHB027_04_M.G...wav',
    'LAI_2015_05_30_MMR019_01_M.VG..PipePipe.wav',
    'LAI_2015_05_30_WHW001_07_F.G.LAI_2015_05_30_WHW001A..wav',
    'LBI_2016_04_05_BAE014_02_M.VG.LBI_2016_04_05_BAE014A.SingleNotesDiffFrequencies.wav',
    'LBI_2016_04_05_BAE015_08_F.EX.LBI_2016_04_05_BAE015A.StutterDiffEnding.wav',
    'LBI_2016_04_05_BAE017_02_F.EX..StutterSong.wav',
    'LBI_2016_04_05_BAE018_01_M.EX..DoubleSyrinxMaybe.wav',
    'LBI_2016_04_05_BAE018_04_M.EX..Clear.wav',
    'LBI_2016_04_06_BAE027_01_F.VG..stutterShortSongLowVol.wav',
    'PKI_2017_02_24_AMH002_06_M.EX.PKI_2017_02_25_AMH002APoss1.LighthouseType.wav',
    'PKI_2017_02_24_AMH010_08_F.EX.PKI_2017_02_25_AMH010Bposs..wav',
    'PKI_2017_02_24_MMR032_11_M.EX.PKI_2017_02_24_MMR032A..wav',
    'PKI_2017_02_24_MMR032_18_M.VG.PKI_2017_02_24_MMR032B..wav',
    'PKI_2017_02_24_WHW006_02_F.EX.PKI_2017_02_24_WHW006A..wav',
    'PKI_2017_02_24_WHW011_01_M.VG.PKI_2017_02_24_WHW011A.LastclickSeemsMicNotBill.wav',
    'PKI_2017_02_26_AMH018_01_F.EX.PKI_2017_02_26_AMH018A.Twiddle.wav',
    'PKI_2017_02_26_MMR029_02_M.VG.PKI_2017_02_26_MMR029A.ClickWarbles.wav',
    'PKI_2017_02_27_WHW008_02_F.VG.PKI_2017_02_27_WHW007A..wav',
    'TAW_2016_09_06_WHW011_12_M.EX.TAW_2016_09_06_WHW011B..wav',
    'TAW_2016_09_07_WHW005_11_M.G.TAW_2016_09_07_WHW005A.WorriedWhistlePipe.wav',
    'TAW_2016_09_07_WHW016_09_M.G..SingleGhhhew.wav',
    'TMI_2012_11_27_MMR006_01_F.G.BkY-GM.(A).wav',
    'TMI_2013_04_29_MMR041_02_M.VG..wav',
    'TMI_2013_10_16_MMR144_01_M.VG.OW-GyM.wav',
    'TMI_2014_12_30_MMR138_01_F.VG.RBr-BM.wav'
]


def read_variables(save_to):
    with zipfile.ZipFile(save_to, 'r', zipfile.ZIP_BZIP2, False) as zip_file:
        content = zip_file.read('variables')
        content = str(content, "utf-8")
        variables = json.loads(content)
    return variables


def extract_psd(extractor, audio_file):
    """
    Extract audio file's spectrogram given its ID
    :param audio_file:
    :param extractor:
    :return: the normalised spectrogram (spectrogram - wise, not dimension wise)
    """
    wav_file_path = wav_path(audio_file)
    spect = extractor(wav_file_path, audio_file.fs, 0, None)
    spect_min = np.min(spect)
    spect_max = np.max(spect)

    return (spect - spect_min) / (spect_max - spect_min)


def create_traning_set(audio_file_id, seg_info, wav_path, spect_path, mask_path, f0_dir, extractor, normalise, window_len, step_size=1):
    noverlap = window_len - step_size
    fs, length = get_wav_info(wav_path)
    duration_ms = int(length * 1000 / fs)
    if not os.path.isfile(spect_path):
        spect = extractor(wav_path, fs, 0, None)
        if normalise:
            spect_min = spect.min()
            spect_max = spect.max()
            spect_range = spect_max - spect_min
            spect = (spect - spect_min) / spect_range

        with open(spect_path, 'wb') as f:
            pickle.dump(spect, f)

        height, width = spect.shape
        mask_img = np.zeros((height, width))

        for seg_id, begin_ms, end_ms in seg_info:
            seg_start_frame = int(begin_ms / duration_ms * width)
            seg_end_frame = int(end_ms / duration_ms * width)

            seg_duration_frame = seg_end_frame - seg_start_frame

            f0_file_path = os.path.join(f0_dir, seg_id + '.pkl')

            with open(f0_file_path, 'rb') as f:
                f0 = pickle.load(f)['binary']
                h_f0, w_f0 = f0.shape
                f0 = f0.astype(float)

                f0 = zoom(f0, (height / h_f0, seg_duration_frame / w_f0))

            f0 = np.where(f0 > 0.5, 1, 0)

            mask_img[:, seg_start_frame:seg_end_frame] = f0

        with open(mask_path, 'wb') as f:
            pickle.dump(mask_img, f)

    else:
        with open(spect_path, 'rb') as f:
            spect = pickle.load(f)
        height, width = spect.shape

    nwindows, windows = split_segments(width, window_len, noverlap, incltail=False)
    profiles = {}
    for beg, end in windows:
        windowed_id = '{}_{}'.format(audio_file_id, beg)
        profiles[windowed_id] = (spect_path, beg, end, mask_path)

    return profiles


def read_tsv_into_dict(tsv_file_path):
    tsv_file_content = pd.read_csv(tsv_file_path, sep='\t')
    filename_2_seg_info = {}
    for seg_id, filename, begin_ms, end_ms in tsv_file_content.values:
        if filename not in filename_2_seg_info:
            seg_info = []
            filename_2_seg_info[filename] = seg_info
        else:
            seg_info = filename_2_seg_info[filename]
        seg_info.append([seg_id, begin_ms, end_ms])

    return filename_2_seg_info


def prepare_samples(wav_dir, spect_dir, mask_dir, f0_dir, tsv_file_path, format, normalise, window_len):
    filename_2_seg_info = read_tsv_into_dict(tsv_file_path)
    extractor = extractors[format]
    input_dims = None
    all_profiles = {}
    for af_name in good_audio_file_name:
        seg_info = filename_2_seg_info[af_name]
        audio_file_id = seg_info[0][0].split('_')[0]

        spect_path = os.path.join(spect_dir, '{}.{}'.format(audio_file_id, format))
        wav_path = os.path.join(wav_dir, af_name)
        mask_path = os.path.join(mask_dir, '{}.{}'.format(audio_file_id, 'mask'))

        profiles = create_traning_set(audio_file_id, seg_info, wav_path, spect_path, mask_path, f0_dir, extractor,
                                      normalise, window_len)
        all_profiles.update(profiles)

        if input_dims is None:
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                input_dims = spect.shape[0]
    return all_profiles, input_dims


def save_variables(variables, all_profiles, input_dims, save_to):
    sids = list(all_profiles.keys())
    variables['sids'] = sids
    variables['profiles'] = all_profiles
    variables['input_dims'] = input_dims
    # variables['output_dims'] = 10

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
    topology = variables['topology']
    batch_size = variables['batch_size']
    n_iterations = variables['n_iterations']
    keep_prob = variables['keep_prob']
    profiles = variables['profiles']

    batch_index_limits = dict(train=n_train, test=n_test)
    sids_collections = dict(train=sids_for_training, test=sids_for_testing)

    spects = {}
    masks = {}
    windows_masked = {}

    @profile  # noqa F821
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

        input_spects = []
        output_masks = []

        for sid in batch_ids:
            filepath, beg, end, mask_path = profiles[sid]

            if filepath in spects:
                file_spect = spects[filepath]
            else:
                with open(filepath, 'rb') as f:
                    file_spect = pickle.load(f)
                    spects[filepath] = file_spect

            if mask_path in masks:
                file_mask = masks[mask_path]
            else:
                with open(mask_path, 'rb') as f:
                    file_mask = pickle.load(f)
                    masks[mask_path] = file_mask

            windowed_spect = file_spect[:, beg:end].T
            windowed_mask = file_mask[:, beg:end].T

            input_spects.append(windowed_spect)
            output_masks.append(windowed_mask)

        return input_spects, output_masks, final_batch

    def train_batch_gen(batch_size):
        return get_batch(batch_size, 'train')

    def test_batch_gen(batch_size):
        return get_batch(batch_size, 'test')

    factory = NDMLPFactory()
    factory.set_output(save_to)
    factory.lrtype = variables['lrtype']
    factory.lrargs = variables['lrargs']
    factory.input_dim = variables['input_dims']
    factory.output_dim = variables['output_dims']
    factory.keep_prob = keep_prob
    factory.stop_pad_length = 0
    factory.go_token = -1
    factory.layer_sizes = infer_topology(topology, variables['input_dims'])
    mlp = factory.build()
    mlp.train(train_batch_gen, test_batch_gen, batch_size=batch_size, n_iterations=n_iterations, display_step=100,
              save_step=100)


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
        parser.add_argument('--wav-dir', action='store', dest='wav_dir', required=True, type=str,
                            help='Path to the directory where audio reside', )
        parser.add_argument('--f0-dir', action='store', dest='f0_dir', required=True, type=str,
                            help='Target path to store the spect features')
        parser.add_argument('--format', action='store', dest='format', required=True, type=str)
        parser.add_argument('--normalised', action='store_true', dest='normalised', default=False)
        parser.add_argument('--work-dir', action='store', dest='work_dir', required=True, type=str,
                            help='Path to the directory where spect and mask will be saved', )
        parser.add_argument('--tsv-file', action='store', dest='tsv_file', required=True, type=str,
                            help='Path to tsv file')
        parser.add_argument('--save-to', action='store', dest='save_to', required=True, type=str)
        parser.add_argument('--window-len', action='store', dest='window_len', required=True, type=int)
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
        save_to = options['save_to']
        work_dir = options['work_dir']
        format = options['format']
        batch_size = options['batch_size']
        window_len = options['window_len']
        n_iterations = options['n_iterations']
        lrtype = options['lrtype']
        lrargs = json.loads(options['lrargs'])
        keep_prob = options['keep_prob']
        topology = infer_topology(options['topology'])
        normalised = options['normalised']
        f0_dir = options['f0_dir']
        tsv_file = options['tsv_file']

        if not save_to.lower().endswith('.zip'):
            save_to += '.zip'

        spect_dir = os.path.join(work_dir, 'spect')
        mask_dir = os.path.join(work_dir, 'mask')

        mkdirp(spect_dir)
        mkdirp(mask_dir)

        all_profiles, input_dims = prepare_samples(wav_dir, spect_dir, mask_dir, f0_dir, tsv_file, format, normalised, window_len)

        input_dims = input_dims * options['window_len']

        if os.path.isfile(save_to):
            info('===========CONTINUING===========')
            variables = read_variables(save_to)
            variables['profiles'] = all_profiles
            # assert variables['input_dims'] == input_dims, 'Saved file content is different from expected.'
            if 'format' in variables:
                assert variables['format'] == format, 'Saved file content is different from expected.'
            else:
                variables['format'] = format
            if 'topology' in variables:
                assert variables['topology'] == topology, 'Saved file content is different from expected.'
            else:
                variables['topology'] = topology
            if 'keep_prob' in variables:
                assert variables['keep_prob'] == keep_prob, 'Saved file content is different from expected.'
            else:
                variables['keep_prob'] = keep_prob

        else:
            mkdirp(work_dir)
            variables = dict(current_batch_index=dict(train=0, test=0), spect_dir=work_dir, format=format,
                             topology=topology, keep_prob=keep_prob, output_dims=input_dims)
            save_variables(variables, all_profiles, input_dims, save_to)

        # These variables can be changed when resuming a saved file
        variables['batch_size'] = batch_size
        variables['n_iterations'] = n_iterations
        variables['lrtype'] = lrtype
        variables['lrargs'] = lrargs

        train(variables, save_to)

