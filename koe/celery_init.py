from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
import celery
import celery.bin.base
import celery.bin.celery
import celery.platforms

# set the default Django settings module for the 'celery' program.
# from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koe.celery_settings')

app = Celery('koe')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

status = celery.bin.celery.CeleryCommand.commands['status']()
status.app = status.get_app()


def celery_is_up():
    try:
        status.run()
        return True
    except celery.bin.base.Error as e:
        if e.status == celery.platforms.EX_UNAVAILABLE:
            return False
        raise e


def delay_in_production(func, *args, **kwargs):
    if celery_is_up():
        func.delay(*args, **kwargs)
    else:
        func(*args, **kwargs)
