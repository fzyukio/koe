"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import json
import os
import pickle
from collections import OrderedDict

import pandas as pd

import numpy as np
from django.core.management.base import BaseCommand
from django.db.models import Case
from django.db.models import F
from django.db.models import When
from progress.bar import Bar

from koe.features.feature_extract import feature_map
from koe.management.commands.run_rnn_encoder import read_variables
from koe.ml.nd_mlp import NDMLPFactory
from koe.model_utils import get_or_error
from koe.models import Segment, Database, DataMatrix, AudioFile
from koe.spect_utils import extractors, psd2img, binary_img, load_global_min_max
from koe.ts_utils import ndarray_to_bytes
from koe.utils import wav_path, split_segments, get_wav_info
from root.utils import mkdirp, zip_equal

from scipy.ndimage.interpolation import zoom


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




def spect_from_seg(seg, extractor):
    af = seg.audio_file
    wav_file_path = wav_path(af)
    fs = af.fs
    start = seg.start_time_ms
    end = seg.end_time_ms
    return extractor(wav_file_path, fs=fs, start=start, end=end)


def encode_syllables(variables, encoder, session, segs, kernel_only):
    num_segs = len(segs)
    batch_size = 200
    extractor = variables['extractor']
    denormalised = variables['denormalised']
    global_max = variables.get('global_max', None)
    global_min = variables.get('global_min', None)
    global_range = global_max - global_min

    num_batches = num_segs // batch_size
    if num_segs / batch_size > num_batches:
        num_batches += 1

    seg_idx = -1
    encoding_result = {}

    bar = Bar('', max=num_segs)

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_segs - (batch_size * batch_idx)

        bar.message = 'Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size)

        lengths = []
        batch_segs = []
        spects = []
        for idx in range(batch_size):
            seg_idx += 1
            seg = segs[seg_idx]
            batch_segs.append(seg)
            spect = spect_from_seg(seg, extractor)
            if denormalised:
                spect = (spect - global_min) / global_range

            dims, length = spect.shape
            lengths.append(length)
            spects.append(spect.T)
            bar.next()
        encoded = encoder.encode(spects, session=session, kernel_only=kernel_only)

        for encod, seg, length in zip_equal(encoded, batch_segs, lengths):
            encoding_result[seg.id] = encod

        bar.finish()
    return encoding_result


def reconstruct_syllables(variables, encoder, session, segs):
    tmp_dir = variables['tmp_dir']
    f0_dir = variables['f0_dir']

    num_segs = len(segs)
    batch_size = 200
    spect_dir = variables['spect_dir']

    is_log_psd = variables['is_log_psd']

    num_batches = num_segs // batch_size
    if num_segs / batch_size > num_batches:
        num_batches += 1

    reconstruction_result = {}

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_segs - (batch_size * batch_idx)

        print('Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size))

        lengths = []
        batch_segs = []
        spects = []
        spect_paths = []
        f0_paths = []

        for idx in range(batch_size):
            seg_id = segs[idx]
            spect_path = os.path.join(spect_dir, '{}.{}'.format(seg_id, 'spect'))
            f0_path = os.path.join(f0_dir, '{}.{}'.format(seg_id, 'pkl'))

            spect_paths.append(spect_path)
            f0_paths.append(f0_path)

            batch_segs.append(seg_id)

            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)

            dims, length = spect.shape
            lengths.append(length)
            spects.append(spect.T)

        reconstructed = encoder.predict(spects, session=session, res_len=lengths)

        for spect, recon, seg_id, length in zip_equal(spects, reconstructed, batch_segs, lengths):
            spect = spect[:length, :].T

            f0_path = os.path.join(f0_dir, '{}.{}'.format(seg_id, 'pkl'))
            h_spect, w_spect = spect.shape
            with open(f0_path, 'rb') as f:
                f0 = pickle.load(f)['binary']
                h_f0, w_f0 = f0.shape
                f0 = f0.astype(float)

                f0 = zoom(f0, ((h_spect * 1.0) / h_f0, (w_spect * 1.0) / w_f0))

            f0 = np.where(f0 < 0.5, 1, 0)
            recon = recon[:length, :].T
            recon = np.where(recon < 0.5, 1, 0)

            origi_path = os.path.join(tmp_dir, '{}-origi.png'.format(seg_id))
            recon_path = os.path.join(tmp_dir, '{}-recon.png'.format(seg_id))
            gt_path = os.path.join(tmp_dir, '{}-gt.png'.format(seg_id))
            psd2img(spect, origi_path, is_log_psd)
            binary_img(recon, recon_path, is_log_psd)
            binary_img(f0, gt_path, is_log_psd)

            reconstruction_result[seg_id] = ('{}-origi.png'.format(seg_id), '{}-recon.png'.format(seg_id), '{}-gt.png'.format(seg_id))
    return reconstruction_result


def encode_into_datamatrix(variables, encoder, session, database_name, kernel_only):
    with_duration = variables['with_duration']
    dm_name = variables['dm_name']
    ndims = encoder.latent_dims

    database = get_or_error(Database, dict(name__iexact=database_name))
    audio_files = AudioFile.objects.filter(database=database)
    segments = Segment.objects.filter(audio_file__in=audio_files)

    encoding_result = encode_syllables(variables, encoder, session, segments, kernel_only)
    features_value = np.array(list(encoding_result.values()))
    sids = np.array(list(encoding_result.keys()), dtype=np.int32)

    sid_sorted_inds = np.argsort(sids)
    sids = sids[sid_sorted_inds]
    features_value = features_value[sid_sorted_inds]

    preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(sids)])
    segments = segments.order_by(preserved)
    tids = segments.values_list('tid', flat=True)

    features = [feature_map['s2s_autoencoded']]
    col_inds = {'s2s_autoencoded': [0, ndims]}
    if with_duration:
        features.append(feature_map['duration'])
        col_inds['duration'] = [ndims, ndims + 1]
        durations = list(segments.annotate(duration=F('end_time_ms') - F('start_time_ms'))
                         .values_list('duration', flat=True))
        durations = np.array(durations)
        assert len(durations) == len(sids)
        features_value = np.concatenate((features_value, durations.reshape(-1, 1)), axis=1)

    features_value = features_value.astype(np.float32)

    dm = DataMatrix(database=database)
    dm.name = dm_name
    dm.ndims = ndims
    dm.features_hash = '-'.join([str(x.id) for x in features])
    dm.aggregations_hash = ''
    dm.save()

    full_sids_path = dm.get_sids_path()
    full_tids_path = dm.get_tids_path()
    full_bytes_path = dm.get_bytes_path()
    full_cols_path = dm.get_cols_path()

    ndarray_to_bytes(features_value, full_bytes_path)
    ndarray_to_bytes(np.array(sids, dtype=np.int32), full_sids_path)
    ndarray_to_bytes(np.array(tids, dtype=np.int32), full_tids_path)

    with open(full_cols_path, 'w', encoding='utf-8') as f:
        json.dump(col_inds, f)


def reconstruction_html(reconstruction_result):
    html_lines = ['''
<tr>
    <th>ID</th>
    <th>Spect</th>
    <th>Pridected_F0</th>
    <th>GT_F0</th>
</tr>
    ''']
    for sid, (origi_path, recon_path, gt_path) in reconstruction_result.items():
        html_lines.append(
            '''
            <tr>
                <td>{}</td>
                <td><img src="{}"/></td>
                <td><img src="{}"/></td>
                <td><img src="{}"/></td>
            </tr>
            '''.format(sid, origi_path, recon_path, gt_path)
        )

    html = '''
<table style="width:100%">
{}
</table>
    '''.format(''.join(html_lines))
    return html

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


def cascade_window(spect, window_len, step_size=1):
    noverlap = window_len - step_size
    height, width = spect.shape
    nwindows, windows = split_segments(width, window_len, noverlap, incltail=False)
    input_segments = []
    for beg, end in windows:
        windowed_spect = spect[:, beg:end].T
        input_segments.append(windowed_spect)

    return input_segments


def merge_cascaded_output(output_masks, window_len, step_size=1):
    num_masks = len(output_masks)
    num_freq_bins = len(output_masks[0]) // window_len

    mask_img_width = window_len + (num_masks - 1) * step_size

    mask_img = np.zeros([num_freq_bins, mask_img_width])
    mask_weights = np.zeros([1, mask_img_width])

    mask_begin_ind = 0
    for i in range(num_masks):
        output_mask = output_masks[i].reshape(-1, num_freq_bins).T
        mask_end_ind = mask_begin_ind + window_len
        mask_img[:, mask_begin_ind:mask_end_ind] += output_mask
        mask_weights[:, mask_begin_ind:mask_end_ind] += 1
        mask_begin_ind += step_size

    mask_img /= mask_weights
    mask_img = np.where(mask_img > 0.5, 1, 0)
    return mask_img


def showcase_reconstruct(variables, encoder, session):
    # test filenames
    filename_2_seg_info_test = variables['filename_2_seg_info']
    for key in good_audio_file_name:
        del filename_2_seg_info_test[key]
    test_audio_file_name = [key for key in filename_2_seg_info_test.keys()][:200]

    tmp_dir = variables['tmp_dir']
    spect_dir = variables['spect_dir']
    wav_dir = variables['wav_dir']
    mask_dir = variables['mask_dir']
    f0_dir = variables['f0_dir']
    window_len = variables['window_len']

    extractor = variables['extractor']

    normalise = True
    for af_name in test_audio_file_name:
        seg_info = filename_2_seg_info_test[af_name]
        audio_file_id = seg_info[0][0].split('_')[0]

        wav_path = os.path.join(wav_dir, af_name)
        fs, length = get_wav_info(wav_path)
        spect = extractor(wav_path, fs, 0, None)
        if normalise:
            spect_min = spect.min()
            spect_max = spect.max()
            spect_range = spect_max - spect_min
            spect = (spect - spect_min) / spect_range

        input_segments = cascade_window(spect, window_len)
        output_masks = encoder.predict(input_segments)

        img_mask = merge_cascaded_output(output_masks, window_len)

        img_spect_path = os.path.join(tmp_dir, audio_file_id+'_spect.png')
        img_mask_path = os.path.join(tmp_dir, audio_file_id+'_mask.png')
        psd2img(spect, img_spect_path, islog=True)
        binary_img(img_mask, img_mask_path)




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

        parser.add_argument('--mode', action='store', dest='mode', default='showcase', type=str)
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)

        parser.add_argument('--tmp-dir', action='store', dest='tmp_dir', required=True, type=str)

        parser.add_argument('--with-duration', action='store_true', dest='with_duration', default=False)
        parser.add_argument('--denormalised', action='store_true', dest='denormalised', default=False)

    def handle(self, *args, **options):
        mode = options['mode']
        load_from = options['load_from']
        tmp_dir = options['tmp_dir']
        f0_dir = options['f0_dir']
        format = options['format']
        with_duration = options['with_duration']
        # min_max_loc = options['min_max_loc']
        denormalised = options['denormalised']

        wav_dir = options['wav_dir']
        # save_to = options['save_to']
        work_dir = options['work_dir']
        format = options['format']
        batch_size = options['batch_size']
        window_len = options['window_len']
        f0_dir = options['f0_dir']
        tsv_file = options['tsv_file']
        tmp_dir = options['tmp_dir']
        extractor = extractors[format]

        spect_dir = os.path.join(work_dir, 'spect')
        mask_dir = os.path.join(work_dir, 'mask')
        mkdirp(spect_dir)
        mkdirp(mask_dir)

        if mode not in ['showcase', 'dm']:
            raise Exception('--mode can only be "showcase" or "dm"')

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'

        if not os.path.isdir(tmp_dir):
            mkdirp(tmp_dir)

        variables = read_variables(load_from)
        variables['tmp_dir'] = tmp_dir
        variables['extractor'] = extractor
        variables['with_duration'] = with_duration
        variables['denormalised'] = denormalised
        variables['f0_dir'] = f0_dir
        variables['window_len'] = window_len
        variables['wav_dir'] = wav_dir

        variables['mask_dir'] = mask_dir
        variables['spect_dir'] = spect_dir

        # if denormalised:
        #     global_min, global_max = load_global_min_max(min_max_loc)
        #     variables['global_min'] = global_min
        #     variables['global_max'] = global_max

        variables['is_log_psd'] = format.startswith('log_')

        filename_2_seg_info = read_tsv_into_dict(tsv_file)
        variables['filename_2_seg_info'] = filename_2_seg_info



        factory = NDMLPFactory()
        factory.set_output(load_from)
        factory.learning_rate = None
        factory.learning_rate_func = None
        encoder = factory.build()
        session = encoder.recreate_session()

        if mode == 'showcase':
            showcase_reconstruct(variables, encoder, session)
        else:
            pass
            # encode_into_datamatrix(variables, encoder, session, database_name, kernel_only)

        session.close()
