"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import os
import pickle
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from progress.bar import Bar
from scipy.ndimage.interpolation import zoom

from koe.spect_utils import psd2img, binary_img, extract_spect
from koe.utils import wav_path, get_wav_info
from root.utils import zip_equal


def spect_from_seg(seg, extractor):
    af = seg.audio_file
    wav_file_path = wav_path(af)
    fs = af.fs
    start = seg.start_time_ms
    end = seg.end_time_ms
    return extractor(wav_file_path, fs=fs, start=start, end=end)


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


def showcase_reconstruct(variables, encoder, session):
    tmp_dir = variables['tmp_dir']
    sids_for_training = variables['sids_train'][:200]
    sids_for_testing = variables['sids_test'][:200]


    constructions = OrderedDict()

    constructions['Syllables used to train'] = sids_for_training
    constructions['Syllables used to test'] = sids_for_testing

    htmls = {}
    for name, sids in constructions.items():
        reconstruction_result = reconstruct_syllables(variables, encoder, session, sids)
        html = reconstruction_html(reconstruction_result)
        #
        # reconstruction_result = reconstruct_syllables(variables, encoder, session, sids)
        # html = reconstruction_html(reconstruction_result)
        htmls[name] = html

    with open(os.path.join(tmp_dir, 'reconstruction_result.html'), 'w') as f:
        for name, html in htmls.items():
            f.write('<h1>Reconstruction of: {}</h1>'.format(name))
            f.write(html)


def showcase_spect_f0(tsv_file, wav_dir, f0_dir, spect_dir):
    csv_file_content = pd.read_csv(tsv_file, sep='\t')

    csv_lines = [x for x in csv_file_content.values]
    wav_file_paths = list(Path(wav_dir).rglob('*.wav'))[:100]

    bar = Bar('Exporting segments ...', max=len(csv_lines))

    for wav_file_path in wav_file_paths:
        wav_filename = str(wav_file_path).split('/')[-1]
        fs, length = get_wav_info(str(wav_file_path))
        duration_ms = length * 1000 // fs
        img_spect_path = '/tmp/' + wav_filename[:-4]+'_spect.png'
        img_f0_path = '/tmp/' + wav_filename[:-4] + '_f0.png'

        spect = extract_spect(wav_file_path, fs, 0, None)
        psd2img(spect, img_spect_path)
        height, width = spect.shape
        img_f0 = np.zeros((height, width))
        f0_records = [x for x in csv_lines if x[1] == wav_filename]

        for f0_record in f0_records:
            seg_id, filename, seg_start_ms, seg_end_ms = f0_record
            seg_start_frame = int(seg_start_ms / duration_ms * width)
            seg_end_frame = int(seg_end_ms / duration_ms * width)

            seg_duration_frame = seg_end_frame - seg_start_frame

            f0_file_path = Path(f0_dir, seg_id + '.pkl')

            with open(f0_file_path, 'rb') as f:
                f0 = pickle.load(f)['binary']
                h_f0, w_f0 = f0.shape
                f0 = f0.astype(float)

                f0 = zoom(f0, (height / h_f0, seg_duration_frame / w_f0))

            f0 = np.where(f0 > 0.5, 1, 0)

            img_f0[:, seg_start_frame:seg_end_frame] = f0

        binary_img(img_f0, img_f0_path)

    bar.finish()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--wav-dir', action='store', dest='wav_dir', required=False, type=str,
                            help='Path to the directory where wav files reside')
        parser.add_argument('--tsv-file', action='store', dest='tsv_file', required=True, type=str,
                            help='Path to tsv file')
        parser.add_argument('--f0-dir', action='store', dest='f0_dir', required=True, type=str,
                            help='Target path to store the spect features')
        parser.add_argument('--spect-dir', action='store', dest='spect_dir', required=True, type=str,
                            help='Target path to store the spect features')

    def handle(self, *args, **options):
        wav_dir = options['wav_dir']
        tsv_file = options['tsv_file']
        f0_dir = options['f0_dir']
        spect_dir = options['spect_dir']

        showcase_spect_f0(tsv_file, wav_dir, f0_dir, spect_dir)
