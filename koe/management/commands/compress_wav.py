"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""
import os
from logging import warning

import pydub
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.models import AudioFile
from root.utils import audio_path, ensure_parent_folder_exists


def convert(conversion_scheme, print_stats=True):
    wav_file_path = conversion_scheme['wav']
    if not os.path.isfile(wav_file_path):
        warning('File {} does not exist, skip.'.format(wav_file_path))
        return

    fmt, filepath = conversion_scheme['other']

    wav_audio = None

    if not os.path.isfile(filepath):
        ensure_parent_folder_exists(filepath)
        wav_audio = pydub.AudioSegment.from_file(wav_file_path)
        wav_audio.export(filepath, format=fmt)

    if print_stats:
        if wav_audio is None:
            wav_audio = pydub.AudioSegment.from_file(wav_file_path)
        wav_size = os.path.getsize(wav_file_path) / 1024 / 1024
        wav_length = len(wav_audio.raw_data) // wav_audio.frame_width
        wav_fs = wav_audio.frame_rate
        file_size = os.path.getsize(filepath) / 1024 / 1024

        converted_file = pydub.AudioSegment.from_file(filepath)
        file_length = len(converted_file.raw_data) // converted_file.frame_width
        file_fs = converted_file.frame_rate

        print('Wav size: {:6.2f}, {} size: {:6.2f}'.format(wav_size, fmt, file_size))
        print('Wav length: {:6.2f}, {} length: {:6.2f}'.format(wav_length, fmt, file_length))
        print('Wav fs: {:6.2f}, {} fs: {:6.2f}'.format(wav_fs, fmt, file_fs))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--wav-file',
            action='store',
            dest='testfile',
            required=False,
            type=str,
            help='Must be a .wav file. If exist, will run conversion test for this file only. '
                 'If not, convert everything.',
        )

        parser.add_argument(
            '--format',
            action='store',
            dest='fmt',
            required=True,
            type=str,
            help='Audio format to convert, e.g. mp3,mp4,ogg. Not all formats are supported',
        )

    def handle(self, testfile, fmt, *args, **options):

        if testfile is None:
            audio_file_names = AudioFile.objects.all().values_list('name', flat=True)

            conversion_list = []

            for name in audio_file_names:
                wav_file_path = audio_path(name, 'wav')
                conversion_scheme = dict(wav=wav_file_path)

                target_file_path = audio_path(name, fmt)
                conversion_scheme['other'] = (fmt, target_file_path)

                conversion_list.append(conversion_scheme)

            bar = Bar('Converting song ...', max=len(conversion_list))
            for conversion_scheme in conversion_list:
                convert(conversion_scheme, print_stats=False)

                bar.next()
            bar.finish()
        else:
            wav_file_path = audio_path(testfile, 'wav')
            target_file_path = '/tmp/test-compress-wav.' + fmt
            conversion_scheme = dict(wav=wav_file_path, other=(fmt, target_file_path))

            convert(conversion_scheme)

            os.remove(target_file_path)
