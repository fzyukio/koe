import sys
from django.db import migrations


def fix_negative_timestamps(apps, schema_editor):
    """ """
    db_alias = schema_editor.connection.alias
    segment_model = apps.get_model("koe", "Segment")

    segments = segment_model.objects.using(db_alias).filter(start_time_ms__lt=0)
    segments.update(start_time_ms=0)

    sys.stdout.write("\n")
    sys.stdout.write(
        "Found {} segments with negative start time and reset to 0.".format(
            len(segments)
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("koe", "0028_audiofile_num_channels"),
    ]

    operations = [
        migrations.RunPython(
            fix_negative_timestamps, reverse_code=migrations.RunPython.noop
        ),
    ]
