import os
import sys

from bulk_update.helper import bulk_update
from django.conf import settings
from django.db import migrations, models

from koe.wavfile import get_wav_info


def add_noc_to_audio_files(apps, schema_editor):
    """
    """
    db_alias = schema_editor.connection.alias
    audio_file_model = apps.get_model('koe', 'AudioFile')

    original_audio_files = audio_file_model.objects.using(db_alias).filter(original=None)
    inoriginal_audio_files = audio_file_model.objects.using(db_alias).exclude(original=None)

    afid_to_noc = {}

    slashed_url = os.path.join(settings.MEDIA_URL, 'audio/wav/{}', '{}.wav')
    unslashed_url = slashed_url[1:]
    wav_path_template = os.path.join(settings.BASE_DIR, unslashed_url)

    sys.stdout.write('\n')
    sys.stdout.write('\tAdding number of channels to {} original AudioFiles...'.format(len(original_audio_files)))

    for audio_file in original_audio_files:
        database_id = audio_file.database.id
        file_name = audio_file.name
        file_path = wav_path_template.format(database_id, file_name)

        if os.path.isfile(file_path):
            _, _, noc = get_wav_info(file_path, return_noc=True)
        else:
            noc = 1
        afid_to_noc[audio_file.id] = noc

        audio_file.noc = noc

    bulk_update(original_audio_files, update_fields=['noc'], batch_size=10000)
    sys.stdout.write('Done\n')
    sys.stdout.write('\tAdding number of channels to {} dependent AudioFiles...'.format(len(inoriginal_audio_files)))

    for audio_file in inoriginal_audio_files:
        original_afid = audio_file.original.id
        audio_file.noc = afid_to_noc[original_afid]

    bulk_update(inoriginal_audio_files, update_fields=['noc'], batch_size=10000)


class Migration(migrations.Migration):
    dependencies = [
        ('koe', '0027_audiofile_added'),
    ]

    operations = [
        migrations.AddField(
            model_name='audiofile',
            name='noc',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),

        migrations.RunPython(add_noc_to_audio_files, reverse_code=migrations.RunPython.noop),

        migrations.AlterField(
            model_name='audiofile',
            name='noc',
            field=models.IntegerField(),
        ),
    ]
