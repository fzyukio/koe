# Generated by Django 2.0.4 on 2018-10-17 20:21

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("koe", "0014_manual_tid_for_spect"),
    ]

    operations = [
        migrations.AddField(
            model_name="audiofile",
            name="active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="segment",
            name="active",
            field=models.BooleanField(default=True),
        ),
    ]
