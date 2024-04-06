# Generated by Django 2.0.4 on 2019-08-08 05:43

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("koe", "0021_auto_20190529_1033"),
    ]

    operations = [
        migrations.AlterField(
            model_name="temporarydatabase",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name="temporarydatabase",
            unique_together={("chksum", "user"), ("user", "name")},
        ),
    ]
