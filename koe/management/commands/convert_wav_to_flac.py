"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""
import os

import pydub
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.models import AudioFile
from root.utils import audio_path, ensure_parent_folder_exists


class Command(BaseCommand):

    def handle(self, *args, **options):
        audio_file_names = AudioFile.objects.all().values_list('name', flat=True)

        conversion_list = []

        for name in audio_file_names:
            flac_file_path = audio_path(name, 'flac')
            wav_file_path = audio_path(name, 'wav')

            if os.path.isfile(wav_file_path) and not os.path.isfile(flac_file_path):
                conversion_list.append((wav_file_path, flac_file_path))

        bar = Bar('Converting song ...', max=len(conversion_list))
        for wav_file_path, flac_file_path in conversion_list:
            audio = pydub.AudioSegment.from_file(wav_file_path)
            ensure_parent_folder_exists(flac_file_path)
            audio.export(flac_file_path, format='flac')
            bar.next()
        bar.finish()
