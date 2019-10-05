"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import json
import os
from collections import OrderedDict

import numpy as np
from django.core.management.base import BaseCommand
from django.db.models import Case
from django.db.models import F
from django.db.models import When
from progress.bar import Bar

from koe.features.feature_extract import feature_map
from koe.management.commands.run_rnn_encoder import read_variables
from koe.ml.nd_vl_simple_ae import NDSMLPAEFactory
from koe.model_utils import get_or_error
from koe.models import Segment, Database, DataMatrix, AudioFile
from koe.spect_utils import extractors, psd2img, load_global_min_max
from koe.ts_utils import ndarray_to_bytes
from koe.utils import wav_path
from root.utils import mkdirp, zip_equal


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
        encoded = encoder.encode(spects, session=session)

        for encod, seg, length in zip_equal(encoded, batch_segs, lengths):
            encoding_result[seg.id] = encod

        bar.finish()
    return encoding_result


def reconstruct_syllables(variables, encoder, session, segs):
    tmp_dir = variables['tmp_dir']
    extractor = variables['extractor']
    denormalised = variables['denormalised']
    global_max = variables.get('global_max', None)
    global_min = variables.get('global_min', None)
    global_range = global_max - global_min
    num_segs = len(segs)
    batch_size = 200

    is_log_psd = variables['is_log_psd']

    num_batches = num_segs // batch_size
    if num_segs / batch_size > num_batches:
        num_batches += 1

    seg_idx = -1
    reconstruction_result = {}

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_segs - (batch_size * batch_idx)

        print('Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size))

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

        reconstructed = encoder.predict(spects, session=session)

        for spect, recon, seg, length in zip_equal(spects, reconstructed, batch_segs, lengths):
            sid = seg.id
            spect = spect[:length, :].T

            if denormalised:
                recon = recon * global_range + global_min
                spect = spect * global_range + global_min

            origi_path = os.path.join(tmp_dir, '{}-origi.png'.format(sid))
            recon_path = os.path.join(tmp_dir, '{}-recon.png'.format(sid))
            psd2img(spect, origi_path, is_log_psd)
            psd2img(recon, recon_path, is_log_psd)

            reconstruction_result[sid] = ('{}-origi.png'.format(sid), '{}-recon.png'.format(sid))
    return reconstruction_result


def encode_into_datamatrix(variables, encoder, session, database_name):
    with_duration = variables['with_duration']
    dm_name = variables['dm_name']
    ndims = encoder.latent_dims

    database = get_or_error(Database, dict(name__iexact=database_name))
    audio_files = AudioFile.objects.filter(database=database)
    segments = Segment.objects.filter(audio_file__id__in=[x.id for x in audio_files])

    encoding_result = encode_syllables(variables, encoder, session, segments)
    features_value = np.array(list(encoding_result.values()))
    sids = np.array(list(encoding_result.keys()), dtype=np.int32)

    sid_sorted_inds = np.argsort(sids)
    sids = sids[sid_sorted_inds]
    features_value = features_value[sid_sorted_inds]

    preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(sids)])
    segments = segments.order_by(preserved)
    tids = segments.values_list('tid', flat=True)

    features = [feature_map['mlp_autoencoded']]
    col_inds = {'mlp_autoencoded': [0, ndims]}
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


def showcase_reconstruct(variables, encoder, session, database_name=None, database_only=False):
    tmp_dir = variables['tmp_dir']
    sids_for_training = variables['sids_for_training']
    sids_for_testing = variables['sids_for_testing']
    segments_for_training = Segment.objects.filter(id__in=sids_for_training)
    segments_for_testing = Segment.objects.filter(id__in=sids_for_testing)

    constructions = OrderedDict()

    if database_name:
        database = get_or_error(Database, dict(name__iexact=database_name))
        segments = Segment.objects.filter(audio_file__database=database)

        if database_only:
            constructions['Syllables in database {}'.format(database_name)] = segments
        else:
            constructions['Syllables used to train'] = segments_for_training
            constructions['Syllables used to test'] = segments_for_testing

            other_segments = segments.exclude(id__in=sids_for_training + sids_for_testing)
            constructions['Other syllables in database {}'.format(database_name)] = other_segments
    else:
        constructions['Syllables used to train'] = segments_for_training
        constructions['Syllables used to test'] = segments_for_testing

    htmls = {}
    for name, sids in constructions.items():
        reconstruction_result = reconstruct_syllables(variables, encoder, session, sids)
        html = reconstruction_html(reconstruction_result)
        htmls[name] = html

    with open(os.path.join(tmp_dir, 'reconstruction_result.html'), 'w') as f:
        for name, html in htmls.items():
            f.write('<h1>Reconstruction of: {}</h1>'.format(name))
            f.write(html)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--mode', action='store', dest='mode', default='showcase', type=str)
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)

        parser.add_argument('--database-name', action='store', dest='database_name', required=False, type=str)
        parser.add_argument('--database-only', action='store_true', dest='database_only', default=False)
        parser.add_argument('--tmp-dir', action='store', dest='tmp_dir', default='/tmp', type=str)
        parser.add_argument('--dm-name', action='store', dest='dm_name', required=False, type=str)
        parser.add_argument('--format', action='store', dest='format', default='spect', type=str)
        parser.add_argument('--with-duration', action='store_true', dest='with_duration', default=False)
        parser.add_argument('--denormalised', action='store_true', dest='denormalised', default=False)
        parser.add_argument('--min-max-loc', action='store', dest='min_max_loc', default=False)

    def handle(self, *args, **options):
        mode = options['mode']
        database_name = options['database_name']
        database_only = options['database_only']
        load_from = options['load_from']
        tmp_dir = options['tmp_dir']
        dm_name = options['dm_name']
        format = options['format']
        with_duration = options['with_duration']
        min_max_loc = options['min_max_loc']
        denormalised = options['denormalised']

        extractor = extractors[format]

        if database_name is None and database_only:
            raise Exception('only_database must be True when database_name is provided')

        if denormalised and min_max_loc is None:
            raise Exception('If data is denomalised, --min-max-loc must be provided')

        if mode not in ['showcase', 'dm']:
            raise Exception('--mode can only be "showcase" or "dm"')

        if mode == 'showcase':
            if dm_name is not None:
                raise Exception('Can\'t accept --dm-name argument in showcase mode')

        else:
            if dm_name is None:
                raise Exception('Must provide --dm-name argument in dm mode')
            if database_name is None:
                raise Exception('database-name is required in dm mode')

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'

        if not os.path.isdir(tmp_dir):
            mkdirp(tmp_dir)

        variables = read_variables(load_from)
        variables['tmp_dir'] = tmp_dir
        variables['dm_name'] = dm_name
        variables['extractor'] = extractor
        variables['with_duration'] = with_duration
        variables['denormalised'] = denormalised

        if denormalised:
            global_min, global_max = load_global_min_max(min_max_loc)
            variables['global_min'] = global_min
            variables['global_max'] = global_max

        variables['is_log_psd'] = format.startswith('log_')

        factory = NDSMLPAEFactory()
        factory.set_output(load_from)
        factory.learning_rate = None
        factory.learning_rate_func = None
        encoder = factory.build()
        session = encoder.recreate_session()

        if mode == 'showcase':
            showcase_reconstruct(variables, encoder, session, database_name, database_only)
        else:
            encode_into_datamatrix(variables, encoder, session, database_name)

        session.close()
