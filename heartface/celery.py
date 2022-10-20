#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import, unicode_literals
import os
import celery
import raven
from raven.contrib.celery import register_signal, register_logger_signal

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heartface.settings')


class Celery(celery.Celery):
    def on_init(self):
        from django.conf import settings
        if settings.RAVEN_CONFIG:
            client = raven.Client(settings.RAVEN_CONFIG['dsn'])
            # register a custom filter to filter out duplicate logs
            register_logger_signal(client)

            # hook into the Celery error handler
            register_signal(client)


app = Celery('heartface')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
