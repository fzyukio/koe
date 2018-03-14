# Generated by Django 2.0.1 on 2018-03-13 17:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import root.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('koe', '0006_auto_20180217_1549'),
    ]

    operations = [
        migrations.CreateModel(
            name='Database',
            fields=[
                ('id', models.CharField(editable=False, max_length=255, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, root.models.AutoSetterGetterMixin),
        ),
        migrations.CreateModel(
            name='DatabaseAssignment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('permission', models.IntegerField(choices=[(1, 'View'), (2, 'Edit')])),
                ('database', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='koe.Database')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, root.models.AutoSetterGetterMixin),
        ),
    ]