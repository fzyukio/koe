import os

import shutil
from logging import warning

import sys
from django.conf import settings
from django.db import migrations

from koe.utils import get_abs_spect_path
from root.utils import ensure_parent_folder_exists


def rearrange_spectrogram(apps, schema_editor):
    """
    """
    current_spect_dir = os.path.join(settings.MEDIA_URL, 'spect', 'fft', 'syllable')[1:]
    current_abs_spect_dir = os.path.join(settings.BASE_DIR, current_spect_dir)

    if os.path.isdir(current_abs_spect_dir):
        spect_files = os.listdir(current_abs_spect_dir)
        sys.stdout.write('\n')
        sys.stdout.write('\tFound {} spectrograms'.format(len(spect_files)))
        sys.stdout.flush()

        for spect_file in spect_files:
            try:
                tid = int(spect_file[:-4])
            except ValueError:
                warning('\tFile {} is not named correctly and will be deleted'.format(spect_file))
                continue

            current_path = current_abs_spect_dir + '/' + str(tid) + '.png'
            new_path = get_abs_spect_path(tid)

            try:
                shutil.move(current_path, new_path)
            except FileNotFoundError:
                ensure_parent_folder_exists(new_path)
                shutil.move(current_path, new_path)

        shutil.rmtree(current_abs_spect_dir)


class Migration(migrations.Migration):
    dependencies = [
        ('koe', '0030_fix_float32_ieee_type_wav'),
    ]

    operations = [
        migrations.RunPython(rearrange_spectrogram, reverse_code=migrations.RunPython.noop),
    ]
