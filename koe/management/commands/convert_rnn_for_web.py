"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""
import os
import shutil
import unittest

import tensorflow as tf
from django.core.management.base import BaseCommand
from tensorflowjs.converters.converter import main as tfjs_converter

import spect_utils
from koe.ml.nd_vl_s2s_autoencoder import NDS2SAEFactory
from koe.models import RnnSegmentor
from root.utils import data_path, mkdirp


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--load-from', action='store', dest='load_from', required=True, type=str)
        parser.add_argument('--window-len', action='store', dest='window_len', required=True, type=int)
        parser.add_argument('--format', action='store', dest='format', default='spect', type=str)

    def handle(self, *args, **options):
        load_from = options['load_from']
        window_len = options['window_len']
        format = options['format']

        if not load_from.lower().endswith('.zip'):
            load_from += '.zip'

        name_with_ext = os.path.split(load_from)[1]
        name_no_ext = os.path.splitext(name_with_ext)[0]

        intermediate_save = load_from + '.tmp'
        if os.path.exists(intermediate_save):
            shutil.rmtree(intermediate_save)

        save_to = data_path('tfjs-models', name_no_ext)
        mkdirp(save_to)

        factory = NDS2SAEFactory()
        factory.set_output(load_from)
        factory.learning_rate = None
        factory.learning_rate_func = None
        encoder = factory.build()
        session = encoder.recreate_session()

        ops = encoder.inference_decoder_output
        tf.saved_model.simple_save(session, intermediate_save, inputs={
            'input': encoder.input_data,
            'out': encoder.output_data,
            's_token': encoder.start_tokens,
            'go_token': encoder.go_tokens,
            's_len': encoder.sequence_length,
            'mask': encoder.mask,
            'tget_len': encoder.target_sequence_length,
            'src_len': encoder.source_sequence_length,
            'lr': encoder.learning_rate,
            'bz': encoder.batch_size
        }, outputs={'output': ops.rnn_output, })

        session.close()

        with unittest.mock.patch('sys.argv', [
            '--input_format=tf_saved_model',
            '--output_node_names=decode_1/decoder/transpose',
            '--saved_model_tags=serve',
            '--output_json=model.json',
            intermediate_save,
            save_to
        ]):
            tfjs_converter()

        shutil.rmtree(intermediate_save)

        segmentor = RnnSegmentor.objects.filter(name=name_no_ext).first()
        if segmentor is None:
            segmentor = RnnSegmentor()
            segmentor.name = name_no_ext

        segmentor.model_path = load_from
        segmentor.input_dim = encoder.input_dim
        segmentor.window_len = window_len
        segmentor.format = format
        segmentor.nfft = spect_utils.nfft
        segmentor.noverlap = spect_utils.noverlap

        segmentor.save()
