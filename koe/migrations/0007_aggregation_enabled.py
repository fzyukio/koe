# Generated by Django 2.0.4 on 2018-09-29 22:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0006_auto_20180903_0833'),
    ]

    operations = [
        migrations.AddField(
            model_name='aggregation',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
    ]