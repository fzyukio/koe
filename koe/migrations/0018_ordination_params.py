# Generated by Django 2.0.4 on 2019-03-26 02:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("koe", "0017_auto_20190213_2255"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordination",
            name="params",
            field=models.CharField(default="", max_length=255),
        ),
    ]
