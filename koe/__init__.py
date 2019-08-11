from __future__ import absolute_import, unicode_literals

# Load the app config
default_app_config = 'koe.apps.KoeConfig'

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery_init import app as celery_app

__all__ = ('celery_app',)
