# Generated by Django 2.0.4 on 2019-12-01 07:09

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("root", "0002_auto_20190509_0141"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="extraattrvalue",
            index=models.Index(
                fields=["owner_id"], name="root_extraa_owner_i_0c4a1b_idx"
            ),
        ),
    ]
