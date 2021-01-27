import datetime
import os

import pytz
import sys
from django_bulk_update.helper import bulk_update
from django.conf import settings
from django.db import migrations, models


def add_datetime_to_audio_files(apps, schema_editor):
    """
    """
    db_alias = schema_editor.connection.alias
    audio_file_model = apps.get_model('koe', 'AudioFile')

    audio_files = audio_file_model.objects.using(db_alias).all()

    slashed_url = os.path.join(settings.MEDIA_URL, 'audio/wav/{}', '{}.wav')
    unslashed_url = slashed_url[1:]
    wav_path_template = os.path.join(settings.BASE_DIR, unslashed_url)

    sys.stdout.write('\n')
    sys.stdout.write('\tAdding timestamp to {} AudioFiles...'.format(len(audio_files)))

    for audio_file in audio_files:
        if audio_file.original is None:
            database_id = audio_file.database.id
            file_name = audio_file.name
        else:
            database_id = audio_file.original.database.id
            file_name = audio_file.original.name
        file_path = wav_path_template.format(database_id, file_name)

        if os.path.isfile(file_path):
            last_modif_timestamp = os.path.getmtime(file_path)
            last_modif_datetime = datetime.datetime.utcfromtimestamp(last_modif_timestamp)
        else:
            last_modif_datetime = datetime.datetime.utcfromtimestamp(0)
        audio_file.added = pytz.utc.localize(last_modif_datetime)

    bulk_update(audio_files, update_fields=['added'], batch_size=10000)


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0026_database_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='audiofile',
            name='added',
            field=models.DateTimeField(null=True),
        ),

        migrations.RunPython(add_datetime_to_audio_files, reverse_code=migrations.RunPython.noop),

        migrations.AlterField(
            model_name='audiofile',
            name='added',
            field=models.DateTimeField(null=False),
        ),
    ]
