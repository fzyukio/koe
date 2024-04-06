import os
import sys

import pydub
from django.conf import settings
from django.db import migrations

from koe.wavfile import read_wav_info


def convert_wav_f32_to_i32(apps, schema_editor):
    """ """
    db_alias = schema_editor.connection.alias
    audio_file = apps.get_model("koe", "AudioFile")

    afs = audio_file.objects.using(db_alias).filter(original=None)

    slashed_url = os.path.join(settings.MEDIA_URL, "audio/wav/{}", "{}.wav")
    unslashed_url = slashed_url[1:]
    wav_path_template = os.path.join(settings.BASE_DIR, unslashed_url)

    wavs_to_convert = []
    for audio_file in afs:
        database_id = audio_file.database.id
        file_name = audio_file.name
        wav_file_path = wav_path_template.format(database_id, file_name)

        if os.path.isfile(wav_file_path):
            (
                size,
                comp,
                num_channels,
                fs,
                sbytes,
                block_align,
                bitrate,
                bytes,
                dtype,
            ) = read_wav_info(wav_file_path)
            if comp == 3:
                wavs_to_convert.append(wav_file_path)

    sys.stdout.write("\n")
    sys.stdout.write(
        "\t\tFound {} WAV files using IEEE format. Now converting to standard format".format(
            len(wavs_to_convert)
        )
    )

    for wav_file_path in wavs_to_convert:
        audio = pydub.AudioSegment.from_file(wav_file_path)
        audio.export(wav_file_path, format="wav")


class Migration(migrations.Migration):
    dependencies = [
        ("koe", "0029_fix_negative_timestamps"),
    ]

    operations = [
        migrations.RunPython(
            convert_wav_f32_to_i32, reverse_code=migrations.RunPython.noop
        ),
    ]
