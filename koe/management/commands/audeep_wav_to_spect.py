"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""
import os
import pickle
from logging import warning

import numpy as np

from django.core.management.base import BaseCommand

from koe.features.utils import get_spectrogram
from root.exceptions import CustomAssertionError
from root.utils import mkdirp

nfft = 512
noverlap = nfft // 2
win_length = nfft
stepsize = nfft - noverlap


def extract_spect(file_path, spect_path):
    psd = get_spectrogram(file_path, fs=None, start=0, end=None, nfft=nfft, noverlap=noverlap, win_length=nfft,
                          center=False)
    with open(spect_path, 'wb') as f:
        pickle.dump(psd, f)


def persist_segment_spectrogram(location, save_spect_to):
    if not os.path.isdir(location):
        raise CustomAssertionError('{} does not exist or is not a folder'.format(location))

    if os.path.isdir(save_spect_to):
        warning('{} already exists as a folder. It\'s better to extract to a new folder'.format(save_spect_to))
    else:
        mkdirp(save_spect_to)

    file_names = os.listdir(location)

    for file_name in file_names:
        if file_name.lower().endswith('.wav'):
            file_path = os.path.join(location, file_name)
            name_no_ext = file_name[:-4]
            spect_name = name_no_ext + '.spect'
            spect_path = os.path.join(save_spect_to, spect_name)

            if not os.path.isfile(spect_path):
                extract_spect(file_path, spect_path)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--location', action='store', dest='location', required=True, type=str,
                            help='Path to the directory where audio segments reside', )
        parser.add_argument('--spect-dir', action='store', dest='save_spect_to', required=True, type=str,
                            help='Path to the directory where audio segments reside', )

    def handle(self, *args, **options):
        location = options['location']
        save_spect_to = options['save_spect_to']

        persist_segment_spectrogram(location, save_spect_to)
