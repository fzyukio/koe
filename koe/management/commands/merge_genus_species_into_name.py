
import os
from logging import warning

import pydub
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.models import AudioFile
from koe.utils import wav_path, audio_path
from koe.models import Species


class Command(BaseCommand):
    def handle(self, *args, **options):
        speciesall = Species.objects.all()
        for sp in speciesall:
            sp.name = sp.genus + " : " + sp.species
            sp.save()

        print(len(speciesall))
        print("executed successfully!")

