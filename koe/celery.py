# coding: utf-8

from __future__ import absolute_import

import os

from django.conf import settings

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "koe.settings.local")

app = Celery('koe_tasks')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
