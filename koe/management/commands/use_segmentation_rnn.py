"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""
import os
import numpy as np
from PIL import Image

from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.management.commands.run_rnn_encoder import read_variables
from koe.management.commands.run_segmentation_rnn import extract_psd
from koe.ml.nd_vl_s2s_autoencoder import NDS2SAEFactory
from koe.model_utils import get_or_error
from koe.models import Database, AudioFile, Segment
from koe.spect_utils import extractors, psd2img
from koe.utils import wav_path, split_segments
from root.utils import mkdirp


def spect_from_seg(seg, extractor):
    af = seg.audio_file
    wav_file_path = wav_path(af)
    fs = af.fs
    start = seg.start_time_ms
    end = seg.end_time_ms
    return extractor(wav_file_path, fs=fs, start=start, end=end)


def generate_html(segmentation_results):
    html_lines = ['''
<tr>
    <th>ID</th>
    <th>Spect</th>
</tr>
    ''']
    for sid, img_path in segmentation_results.items():
        html_lines.append(
            '''
            <tr>
                <td>{}</td>
                <td><img src="{}"/></td>
            </tr>
            '''.format(sid, img_path)
        )

    html = '''
<table style="width:100%">
{}
</table>
    '''.format(''.join(html_lines))
    return html


def paint_segments(af_spect, correct_segments, auto_segments):
    top_bar = np.full((5, af_spect.shape[1], 3), 255, dtype=np.uint8)
    bottom_bar = np.full((5, af_spect.shape[1], 3), 255, dtype=np.uint8)
    for beg, end in correct_segments:
        top_bar[:, beg:end, :] = [255, 0, 0]

    for beg, end in auto_segments:
        bottom_bar[:, beg:end, :] = [0, 255, 0]
    af_spect = np.concatenate((top_bar, af_spect, bottom_bar), axis=0)
    return af_spect


def run_segmentation(duration_frames, psd, encoder, session, window_len, step_size=1):
    noverlap = window_len - step_size
    nwindows, windows = split_segments(duration_frames, window_len, noverlap, incltail=False)
    mask = np.zeros((duration_frames, ), dtype=np.float32)
    windoweds = []
    lengths = [window_len] * nwindows
    for beg, end in windows:
        windowed = psd[:, beg:end].T
        windoweds.append(windowed)

    predicteds = encoder.predict(windoweds, session, res_len=lengths)
    for predicted, (beg, end) in zip(predicteds, windows):
        predicted_binary = predicted.reshape(window_len) > 0.5
        mask[beg: end] += predicted_binary

    threshold = window_len * 0.3
    syllable_frames = mask > threshold

    syllables = []
    current_syl = None
    opening = False
    for i in range(duration_frames - 1):
        this_frame = syllable_frames[i]
        next_frame = syllable_frames[i + 1]
        if this_frame and next_frame:
            if opening is False:
                opening = True
                current_syl = [i]
        elif this_frame and opening:
            opening = False
            current_syl.append(i)
            syllables.append(current_syl)
            current_syl = None

    return syllables


def showcase_segmentation(variables, encoder, session):
    tmp_dir = variables['tmp_dir']
    extractor = variables['extractor']
    is_log_psd = variables['is_log_psd']
    window_len = variables['window_len']
    database_name = variables['database_name']

    database = get_or_error(Database, dict(name__iexact=database_name))
    audio_files = AudioFile.objects.filter(database=database)

    segmentation_results = {}
    bar = Bar('Extracting spectrogram and show segmentation...', max=len(audio_files))
    for audio_file in audio_files:
        af_id = audio_file.id
        af_psd = extract_psd(extractor, audio_file)
        _, duration_frames = af_psd.shape

        af_spect = psd2img(af_psd, islog=is_log_psd)
        af_duration_ms = int(audio_file.length / audio_file.fs * 1000)
        af_duration_frame = af_spect.shape[1]
        correct_segments = Segment.objects.filter(audio_file=audio_file).values_list('start_time_ms', 'end_time_ms')
        correct_segments = np.array(list(correct_segments)) / af_duration_ms * af_duration_frame
        correct_segments = correct_segments.astype(np.int32)

        auto_segments = run_segmentation(duration_frames, af_psd, encoder, session, window_len)
        af_spect = paint_segments(af_spect, correct_segments, auto_segments)

        img_filename = '{}.png'.format(af_id)
        img_path = os.path.join(tmp_dir, img_filename)

        img = Image.fromarray(af_spect)
        img.save(img_path, format='PNG')

        segmentation_results[af_id] = img_filename
        bar.next()

    html = generate_html(segmentation_results)
    with open(os.path.join(tmp_dir, 'index.html'), 'w') as f:
        f.write(html)
    bar.finish()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str)
        parser.add_argument('--tmp-dir', action='store', dest='tmp_dir', default='/tmp', type=str)
        parser.add_argument('--format', action='store', dest='format', default='spect', type=str)
        parser.add_argument('--window-len', action='store', dest='window_len', required=True, type=int)

    def handle(self, *args, **options):
        database_name = options['database_name']
        load_from = options['load_from']
        tmp_dir = options['tmp_dir']
        format = options['format']
        window_len = options['window_len']

        extractor = extractors[format]

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'

        if not os.path.isdir(tmp_dir):
            mkdirp(tmp_dir)

        variables = read_variables(load_from)
        variables['tmp_dir'] = tmp_dir
        variables['extractor'] = extractor
        variables['is_log_psd'] = format.startswith('log_')
        variables['database_name'] = database_name
        variables['window_len'] = window_len

        factory = NDS2SAEFactory()
        factory.set_output(load_from)
        factory.learning_rate = None
        factory.learning_rate_func = None
        encoder = factory.build()
        session = encoder.recreate_session()

        showcase_segmentation(variables, encoder, session)
        session.close()
