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

import matplotlib
from PIL import Image

from koe.colourmap import cm_red, cm_green, cm_blue
from root.utils import mkdirp

matplotlib.use('TkAgg')

import numpy as np
from django.core.management.base import BaseCommand
from matplotlib import pyplot as plt

from koe.ml.variable_length_s2s_autoencoder import VLS2SAutoEncoderFactory


def spd2img(spd, imgpath):
    """
    Extract raw sepectrograms for all segments (Not the masked spectrogram from Luscinia) of an audio file
    :param audio_file:
    :return:
    """
    height, width = np.shape(spd)
    spd = np.flipud(spd)

    eps = 1e-3
    # find maximum
    spd_max = abs(spd).max()
    # compute 20*log magnitude, scaled to the max
    spd = 20.0 * np.log10(abs(spd) / spd_max + eps)

    min_spect_pixel = spd.min()
    max_spect_pixel = spd.max()
    spect_pixel_range = max_spect_pixel - min_spect_pixel
    interval64 = spect_pixel_range / 63

    spd = ((spd - min_spect_pixel) / interval64)
    spd[np.isinf(spd)] = 0
    spd = spd.astype(np.int)

    spd = spd.reshape((width * height,), order='C')
    spd[spd >= 64] = 63
    spd_rgb = np.empty((height, width, 3), dtype=np.uint8)
    spd_rgb[:, :, 0] = cm_red[spd].reshape((height, width)) * 255
    spd_rgb[:, :, 1] = cm_green[spd].reshape((height, width)) * 255
    spd_rgb[:, :, 2] = cm_blue[spd].reshape((height, width)) * 255
    img = Image.fromarray(spd_rgb)
    img.save(imgpath, format='PNG')


def show_spectrogram(ax, spd):
    eps = 1e-3
    # find maximum
    spd_max = abs(spd).max()
    # compute 20*log magnitude, scaled to the max
    spd_log = 20.0 * np.log10(abs(spd) / spd_max + eps)

    ax.imshow(np.flipud(spd_log), extent=[0, 1, 0, 1], cmap=plt.cm.viridis, aspect='auto')


def correct_lengths(sequences, lengths):
    retval = []
    for sequence, length in zip(sequences, lengths):
        # corrected = sequence.transpose(1, 0)
        corrected = sequence[:length, :]
        retval.append(corrected)
    return retval


def reconstruct_syllable_with_id(variables, encoder, session, sids):
    spect_dir = variables['spect_dir']
    tmp_dir = variables['tmp_dir']
    num_sids = len(sids)
    batch_size = 200

    num_batches = num_sids // batch_size
    if num_sids / batch_size > num_batches:
        num_batches += 1

    sid_idx = -1
    reconstruction_result = {}

    sequences = np.zeros((batch_size, variables['max_length'], variables['dims']))
    mask = np.zeros((batch_size, variables['max_length']), dtype=np.float32)

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_sids - (batch_size * batch_idx)

        print('Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size))

        lengths = []
        batch_sids = []
        for idx in range(batch_size):
            sid_idx += 1
            sid = sids[sid_idx]
            batch_sids.append(sid)
            spect_path = os.path.join(spect_dir, '{}.spect'.format(sid))
            with open(spect_path, 'rb') as f:
                spect = pickle.load(f)
                dims, length = spect.shape
                spect_padded = np.zeros((dims, variables['max_length']), dtype=spect.dtype)
                spect_padded[:, :length] = spect

                sequences[idx, :, :] = spect_padded.T
                mask[idx, :] = 0
                mask[idx, :length] = 1
                lengths.append(length)

        reconstructed = encoder.predict(sequences[:batch_size], lengths, session=session)

        for spect, recon, sid, length in zip(sequences[:batch_size], reconstructed, batch_sids, lengths):
            spect = spect[:length, :].T
            recon = recon[:length, :].T
            origi_path = os.path.join(tmp_dir, '{}-origi.png'.format(sid))
            recon_path = os.path.join(tmp_dir, '{}-recon.png'.format(sid))
            spd2img(spect, origi_path)
            spd2img(recon, recon_path)

            reconstruction_result[sid] = (origi_path, recon_path)

    return reconstruction_result


def read_variables(save_to):
    with zipfile.ZipFile(save_to, 'r', zipfile.ZIP_BZIP2, False) as zip_file:
        variables = json.loads(zip_file.read('variables'))
    return variables


def reconstruction_html(reconstruction_result):
    html_lines = ['''
<tr>
    <th>ID</th>
    <th>Original</th>
    <th>Reconstructed</th>
</tr>
    ''']
    for sid, (origi_path, recon_path) in reconstruction_result.items():
        html_lines.append(
            '''
            <tr>
                <td>{}</td>
                <td><img src="{}"/></td>
                <td><img src="{}"/></td>
            </tr>
            '''.format(sid, origi_path, recon_path)
        )

    html = '''
<table style="width:100%">
{}
</table>
    '''.format(''.join(html_lines))
    return html


def showcase_reconstruct(variables, encoder, session):
    tmp_dir = variables['tmp_dir']
    sids_for_testing = variables['sids_for_testing']
    reconstruction_result_testing_sids = reconstruct_syllable_with_id(variables, encoder, session, sids_for_testing)
    html_testing_sids = reconstruction_html(reconstruction_result_testing_sids)

    sids_for_training = variables['sids_for_training']
    reconstruction_result_training_sids = reconstruct_syllable_with_id(variables, encoder, session, sids_for_training)
    html_training_sids = reconstruction_html(reconstruction_result_training_sids)

    html =\
        '''
<h1>Reconstruct test syllables</h1>
{}
<h1>Reconstruct training syllables</h1>
{}
        '''.format(html_testing_sids, html_training_sids)

    with open(os.path.join(tmp_dir, 'reconstruction_result.html'), 'w') as f:
        f.write(html)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--spect-dir', action='store', dest='spect_dir', required=True, type=str)
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)
        parser.add_argument('--tmp-dir', action='store', dest='tmp_dir', default='/tmp', type=str)

    def handle(self, *args, **options):
        spect_dir = options['spect_dir']
        load_from = options['load_from']
        tmp_dir = options['tmp_dir']

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'

        if not os.path.isdir(spect_dir):
            raise Exception('{} does not exist or does not exist as a folder.'.format(spect_dir))

        if not os.path.isdir(tmp_dir):
            mkdirp(tmp_dir)

        variables = read_variables(load_from)
        variables['spect_dir'] = spect_dir
        variables['tmp_dir'] = tmp_dir

        factory = VLS2SAutoEncoderFactory()
        encoder = factory.build(load_from)
        session = encoder.recreate_session()
        showcase_reconstruct(variables, encoder, session)
