"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""
import json
import numpy as np

from koe.management.commands.run_rnn_encoder import read_variables
from koe.ml.nd_vl_s2s_autoencoder import NDS2SAEFactory
from koe.management.abstract_commands.use_segmentation import UseSegmenter, Segmenter
from koe.utils import split_segments


def run_segmentation(duration_frames, psd, encoder, session, window_len, step_size=1):
    noverlap = window_len - step_size
    nwindows, windows = split_segments(duration_frames, window_len, noverlap, incltail=False)
    mask = np.zeros((duration_frames,), dtype=np.float32)
    windoweds = []
    lengths = [window_len] * nwindows
    psd = psd.T
    for beg, end in windows:
        windowed = psd[beg:end, :]
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

    with open('user_data/tmp/psd.json', 'w') as f:
        json.dump(dict(psd=psd, windoweds=np.array(windoweds).tolist(), predicteds=np.array(predicteds).tolist(),
                       lengths=lengths, syllables=syllables), f)

    return syllables, None


class SeqAutoEncoderSegmenter(Segmenter):
    def __init__(self, variables, encoder, session):
        self.tmp_dir = variables['tmp_dir']
        self.extractor = variables['extractor']
        self.is_log_psd = variables['is_log_psd']
        self.window_len = variables['window_len']
        self.encoder = encoder
        self.session = session

    def get_segment(self, af_psd, audio_file):
        # segmentation_results = {}
        # bar = Bar('Extracting spectrogram and show segmentation...', max=len(audio_files))
        # for audio_file in audio_files:
        #     af_id = audio_file.id
        #     af_psd = extract_psd(extractor, audio_file)
        #
        #     with open('user_data/tmp/psd.json', 'w') as f:
        #         json.dump(dict(psd=np.array(af_psd).tolist(), id=af_id), f)

        _, duration_frames = af_psd.shape
        return run_segmentation(duration_frames, af_psd, self.encoder, self.session, self.window_len)


class Command(UseSegmenter):
    def close(self):
        self.session.close()

    def create_segmenter(self, variables) -> Segmenter:
        load_from = variables['load_from']
        factory = NDS2SAEFactory()
        factory.set_output(load_from)
        factory.learning_rate = None
        factory.learning_rate_func = None
        self.encoder = factory.build()
        self.session = self.encoder.recreate_session()
        return SeqAutoEncoderSegmenter(variables, self.encoder, self.session)

    def create_variables(self, options) -> dict:
        load_from = options['load_from']
        variables = read_variables(load_from)
        variables['load_from'] = load_from
        variables['window_len'] = options['window_len']
        variables['format'] = options['format']
        variables['normalise'] = True
        variables['hipass'] = None
        return variables

    def add_arguments(self, parser):
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)
        parser.add_argument('--window-len', action='store', dest='window_len', required=True, type=int)
        parser.add_argument('--format', action='store', dest='format', default='spect', type=str)

        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        load_from = options['load_from']

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'
            options['load_from'] = load_from

        super(Command, self).handle(*args, **options)
