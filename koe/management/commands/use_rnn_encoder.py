"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import json
import os
import zipfile

import numpy as np
from PIL import Image
from django.core.management.base import BaseCommand
from django.db.models import Case
from django.db.models import F
from django.db.models import When
from progress.bar import Bar

from koe import wavfile
from koe.colourmap import cm_green
from koe.colourmap import cm_red, cm_blue
from koe.features.feature_extract import feature_map
from koe.features.scaled_freq_features import mfcc
from koe.features.utils import get_spectrogram
from koe.ml.nd_vl_s2s_autoencoder import NDS2SAEFactory
from koe.model_utils import get_or_error
from koe.models import Segment, Database, DataMatrix
from koe.ts_utils import ndarray_to_bytes, bytes_to_ndarray, get_rawdata_from_binary
from koe.utils import wav_path
from root.utils import mkdirp

nfft = 512
noverlap = nfft // 2
win_length = nfft
stepsize = nfft - noverlap


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


def extract_spect(wav_file_path, fs, start, end):
    return get_spectrogram(wav_file_path, fs=fs, start=start, end=end, nfft=nfft, noverlap=noverlap, win_length=nfft,
                           center=False)


def extract_mfcc(wav_file_path, fs, start, end):
    sig = wavfile.read_segment(wav_file_path, beg_ms=start, end_ms=end, mono=True)
    args = dict(nfft=nfft, noverlap=noverlap, win_length=win_length, fs=fs, wav_file_path=None, start=0, end=None,
                sig=sig, center=True)
    return mfcc(args)


def spect_from_seg(seg, extractor):
    af = seg.audio_file
    wav_file_path = wav_path(af)
    fs = af.fs
    start = seg.start_time_ms
    end = seg.end_time_ms
    return extractor(wav_file_path, fs=fs, start=start, end=end)


def encode_syllables(variables, encoder, session, segs):
    num_segs = len(segs)
    batch_size = 200
    max_length = variables['max_length']
    extractor = variables['extractor']

    num_batches = num_segs // batch_size
    if num_segs / batch_size > num_batches:
        num_batches += 1

    seg_idx = -1
    encoding_result = {}

    sequences = np.zeros((batch_size, max_length, variables['dims']))
    mask = np.zeros((batch_size, max_length), dtype=np.float32)

    bar = Bar('', max=num_segs)

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_segs - (batch_size * batch_idx)

        bar.message = 'Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size)

        lengths = []
        batch_segs = []
        for idx in range(batch_size):
            seg_idx += 1
            seg = segs[seg_idx]
            batch_segs.append(seg)
            spect = spect_from_seg(seg, extractor)

            dims, length = spect.shape
            spect_padded = np.zeros((dims, max_length), dtype=spect.dtype)

            if length > max_length:
                length = max_length
            spect_padded[:, :length] = spect[:, :length]

            sequences[idx, :, :] = spect_padded.T
            mask[idx, :] = 0
            mask[idx, :length] = 1
            lengths.append(length)
            bar.next()

        encoded = encoder.encode(sequences[:batch_size], lengths, mask, session=session)

        for encod, seg, length in zip(encoded, batch_segs, lengths):
            encoding_result[seg.id] = encod

        bar.finish()
    return encoding_result


def reconstruct_syllables(variables, encoder, session, segs):
    tmp_dir = variables['tmp_dir']
    max_length = variables['max_length']
    extractor = variables['extractor']
    num_segs = len(segs)
    batch_size = 200

    num_batches = num_segs // batch_size
    if num_segs / batch_size > num_batches:
        num_batches += 1

    seg_idx = -1
    reconstruction_result = {}

    sequences = np.zeros((batch_size, max_length, variables['dims']))
    mask = np.zeros((batch_size, max_length), dtype=np.float32)

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_segs - (batch_size * batch_idx)

        print('Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size))

        lengths = []
        batch_segs = []
        for idx in range(batch_size):
            seg_idx += 1
            seg = segs[seg_idx]
            batch_segs.append(seg)
            spect = spect_from_seg(seg, extractor)

            dims, length = spect.shape
            spect_padded = np.zeros((dims, max_length), dtype=spect.dtype)

            if length > max_length:
                length = max_length
            spect_padded[:, :length] = spect[:, :length]
            sequences[idx, :, :] = spect_padded.T
            mask[idx, :] = 0
            mask[idx, :length] = 1
            lengths.append(length)

        reconstructed = encoder.predict(sequences[:batch_size], lengths, mask, session=session)

        for spect, recon, seg, length in zip(sequences[:batch_size], reconstructed, batch_segs, lengths):
            sid = seg.id
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


def encode_into_datamatrix(variables, encoder, session, database_name):
    with_duration = variables['with_duration']
    dm_name = variables['dm_name']
    ndims = encoder.latent_dims

    database = get_or_error(Database, dict(name__iexact=database_name))
    segments = Segment.objects.filter(audio_file__database=database)

    encoding_result = encode_syllables(variables, encoder, session, segments)
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


def showcase_reconstruct(variables, encoder, session, database_name):
    tmp_dir = variables['tmp_dir']

    database = get_or_error(Database, dict(name__iexact=database_name))
    segments = Segment.objects.filter(audio_file__database=database)

    reconstruction_result = reconstruct_syllables(variables, encoder, session, segments)
    html = reconstruction_html(reconstruction_result)

    with open(os.path.join(tmp_dir, 'reconstruction_result.html'), 'w') as f:
        f.write(html)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--mode', action='store', dest='mode', default='showcase', type=str)
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)

        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str)
        parser.add_argument('--tmp-dir', action='store', dest='tmp_dir', default='/tmp', type=str)
        parser.add_argument('--dm-name', action='store', dest='dm_name', required=False, type=str)
        parser.add_argument('--format', action='store', dest='format', default='spect', type=str)
        parser.add_argument('--with-duration', action='store_true', dest='with_duration', default=False)

    def handle(self, *args, **options):
        mode = options['mode']
        database_name = options['database_name']
        load_from = options['load_from']
        tmp_dir = options['tmp_dir']
        dm_name = options['dm_name']
        format = options['format']
        with_duration = options['with_duration']

        if format == 'spect':
            extractor = extract_spect
        else:
            extractor = extract_mfcc

        if mode not in ['showcase', 'dm']:
            raise Exception('--mode can only be "showcase" or "dm"')

        if mode == 'showcase':
            if dm_name is not None:
                raise Exception('Can\'t accept --dm-name argument in showcase mode')

        else:
            if dm_name is None:
                raise Exception('Must provide --dm-name argument in dm mode')

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'

        if not os.path.isdir(tmp_dir):
            mkdirp(tmp_dir)

        variables = read_variables(load_from)
        variables['tmp_dir'] = tmp_dir
        variables['dm_name'] = dm_name
        variables['extractor'] = extractor
        variables['with_duration'] = with_duration

        factory = NDS2SAEFactory()
        encoder = factory.build(load_from)
        session = encoder.recreate_session()

        if mode == 'showcase':
            showcase_reconstruct(variables, encoder, session, database_name)
        else:
            encode_into_datamatrix(variables, encoder, session, database_name)
