# Generated by Django 2.0.4 on 2020-05-24 04:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('koe', '0034_auto_20200511_2031'),
    ]

    operations = [
        migrations.AlterField(
            model_name='segment',
            name='end_time_ms',
            field=models.DecimalField(decimal_places=2, max_digits=11),
        ),
        migrations.AlterField(
            model_name='segment',
            name='start_time_ms',
            field=models.DecimalField(decimal_places=2, max_digits=11),
        ),
    ]
