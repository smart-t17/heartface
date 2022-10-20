#!/usr/bin/env python
# coding=utf-8
import raven

from .deployment import *

# NOTE: ideally this file is (mostly) empty as we want the staging environment to be as close
#  to the production as possible.

ALLOWED_HOSTS = ['heartface.atleta.hu']

SITE_ID = 3
SITE_CONFIG = {
    'name': 'staging',
    'domain': 'heartface.atleta.hu'
}


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'heartface',
        'USER': 'heartface',
        'PASSWORD': 'xxxxxx',
        'HOST': 'localhost',
        'PORT': '5435',
    }
}

RAVEN_CONFIG['dsn'] = ''
