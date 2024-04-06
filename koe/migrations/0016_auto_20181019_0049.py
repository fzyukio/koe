# Generated by Django 2.0.4 on 2018-10-19 00:49

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import root.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("koe", "0015_auto_20181017_2021"),
    ]

    operations = [
        migrations.CreateModel(
            name="Preference",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        editable=False,
                        max_length=255,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("key", models.CharField(max_length=255)),
                ("value", models.TextField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            bases=(models.Model, root.models.AutoSetterGetterMixin),
        ),
        migrations.AlterUniqueTogether(
            name="preference",
            unique_together={("user", "key")},
        ),
    ]
