# Generated by Django 2.0.4 on 2019-05-09 01:41

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("root", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="invitation_code",
        ),
        migrations.DeleteModel(
            name="InvitationCode",
        ),
    ]
