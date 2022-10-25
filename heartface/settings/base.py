"""
Base Django settings for heartface project.

This file contains the base settings that are valid for all environments. The environment
specific settins files can then override these. (See environment.py)

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import sys

from configparser import RawConfigParser
from datetime import timedelta

from django.conf.global_settings import AUTHENTICATION_BACKENDS
from django.urls import reverse_lazy


# TODO: move this into a separate file, probably in libs


def _apply(fn, x, times,):
    if times > 1:
        return fn(_apply(fn, x, times - 1))
    else:
        return fn(x)


PROJECT_ROOT = _apply(os.path.dirname, os.path.abspath(__file__), 3)

PROJECT_NAME = 'heartface'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = r'h!)4!qe6tp8hi+=&_$_*5x%x7u=yq2=sap66l)z9_g9k3r36g!'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

TEMPLATE_DEBUG = DEBUG

# Recipients of traceback emails and other notifications.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

# See: https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

########## DATABASE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    # Sample settings for Postgresql. The actual settings should live in the environment specific
    #  files. For specifying a local development db use local.py
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': '<database_name>',
        'USER': '<user_name>',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '',
    }
}
########## END DATABASE CONFIGURATION

########## CACHE CONFIGURATION
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#             'SOCKET_TIMEOUT': 5,  # in seconds
#             'CONNECTION_POOL_KWARGS': {'max_connections': 100},
#             # Native parser for added performance (can be included later, maybe for deployment only
#             # 'PARSER_CLASS': 'redis.connection.HiredisParser',
#             # 'PASSWORD': 'secretpassword',  # Optional
#         }
#     }
# }
########## END CACHE CONFIGURATION


########## TEMPLATE CONFIGURATION
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_ROOT, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'settings_context_processor.context_processors.settings',
                'django.template.context_processors.csrf',
            ],
            # 'loaders': [
            #     'django.template.loaders.filesystem.Loader',
            #     'django.template.loaders.app_directories.Loader',
            # ],
        }
    },
]

########## END TEMPLATE CONFIGURATION


########## APP CONFIGURATION

# Application definition
# See: https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Useful template tags:
    # 'django.contrib.humanize',

    # Admin panel and documentation:
    'django.contrib.admin',
    # 'django.contrib.admindocs',

    #
    # 3rd party apps:
    #
    #    'easy_thumbnails',
    #    'image_cropping', # -> report missing dependency (easy-thumbnails)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'rest_auth',
    'rest_auth.registration',
    'rest_framework_swagger',
    'adminsortable2',
    'django_countries',

    # Enabled social account providers: (see the complete list here: http://django-allauth.readthedocs.io/en/latest/installation.html)
    'allauth.socialaccount.providers.facebook',

    # Maybe needed for deployment only?
    'compressor',
    'django_forms_bootstrap',
    'rest_framework',
    'rest_framework.authtoken',
    'jsonify',
    'raven.contrib.django.raven_compat',
    'settings_context_processor',
    'django_user_agents',
    'corsheaders',
    'django_celery_beat',

    #
    # Local apps
    #
    'heartface.apps.core.apps.CoreAppConfig',
    'heartface.apps.auth.apps.AuthAppConfig',
    'djstripe',

)
########## END APP CONFIGURATION

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'corsheaders.middleware.CorsPostCsrfMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'cached_auth.Middleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
    'heartface.apps.core.middleware.VersionInfoMiddleware',
)

ROOT_URLCONF = '%s.urls' % PROJECT_NAME

WSGI_APPLICATION = '%s.wsgi.application' % PROJECT_NAME

APPEND_SLASH = True

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

# See: https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = 'en-us'

# See: https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = 'UTC'

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-l10n
USE_L10N = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

########## STATIC FILE CONFIGURATION
# Static files get collected here upon deployment
# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'assets')

# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = '/backend/static/'

# Static files get collected *from* these directories by the FileSystemFinder. (Other finders
#  may collect files from other locations as well.)
# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = (
    os.path.join(PROJECT_ROOT, 'static'),
)

# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)
########## END STATIC FILE CONFIGURATION

########## MEDIA CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')

# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = '/media/'
########## END MEDIA CONFIGURATION


########## SITE CONFIGURATION
# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/1.6/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []
########## END SITE CONFIGURATION

########## SECURITY CONFIGURATION
# Password hashers are in the order of strength. Think about removing the ones that you don't
#  want to use to prevent surprises.
PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

# Disable access to cookies by JavaScript (on most browsers...)
SESSION_COOKIE_HTTPONLY = True

# Set this to true if you are using https
SESSION_COOKIE_SECURE = False

########## END SECURITY CONFIGURATION

########## LOGGING CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#logging
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.

# TODO: add sample sentry config
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(module)s[%(process)d] %(levelname)s -- %(message)s',
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO'
        },
        # 'segment': {
        #     'handlers': ['console'],
        #     'level': 'DEBUG',
        #     'propagate': True,
        # },
    }
}
########## END LOGGING CONFIGURATION

########## REST FRAMEWORK CONFIGURATION
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # JSON Web token is not returned by auth views (rest-auth) yet.
        # 'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 10,
    'SEARCH_PARAM': 'q',
}

########## END REST FRAMEWORK CONFIGURATION

########## AUTHENTICATION CONFIGURATION
AUTH_USER_MODEL = 'core.User'
LOGIN_URL = reverse_lazy('account_login')
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

########## END AUTHENTICATION CONFIGURATION

########## THUMBNAIL CONFIGURATION (used for cropping in admin)
#from easy_thumbnails.conf import Settings as thumbnail_settings
#THUMBNAIL_PROCESSORS = (
#    'image_cropping.thumbnail_processors.crop_corners',
#) + thumbnail_settings.THUMBNAIL_PROCESSORS
#
#IMAGE_CROPPING_THUMB_SIZE = (500, 500)
########## END THUMBNAIL CONFIGURATION

########## BLANC BASIC PAGES CONFIGURATION
PAGE_TEMPLATES = (
    ('pages/default_template.html', 'default'),
)
########## END BLANC BASIC PAGES CONFIGURATION

TEMPLATE_VISIBLE_SETTINGS = (
    'STATIC_URL',
    'VERSION'
)

########## HEARTFACE SPECIFIC SETTINGS
# Sample social account/apps configuration. These settings will be inserted/updated in the db every time the app starts.
# The key is used as both the name and the provider (SocialApp.name). The reason is to avoid confusion as we'll
# (as of now it seems) only ever need one app for each service/provider. Provider is used for looking up and identifying
# the setting in the db.
#
# This config is site specific, so the apps specified below will always be assigned to the current site (see SITE_ID).
#
# The below is only an example, real config needs to be provided in the environment specific settings.

# A placeholder user is needed by some migrations and it may have to be recreated if it has been deleted
MIGRATIONS_PLACEHOLDER_USER_PARAMS = {
    'email': 'placeholder-migrations@dummy.user.no',
    'username': 'migrations@dummy.user.no',
    'is_active': False
}

SOCIAL_APPS = {
    # Key is used as the provider name (relative to allauth.socialaccount.providers package)
    'facebook': {
        'client_id': '...',
        'secret': '...',
        'key': '...'  # Optional
    }
}

SOCIALACCOUNT_PROVIDERS = {
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'INIT_PARAMS': {'cookie': True},
        'FIELDS': [
            'id',
            'email',
            'picture',
            'gender',
            'birthday',
            # 'name',
            # 'first_name',
            # 'last_name',
            # 'verified',
            # 'locale',
            # 'timezone',
            # 'link',
            # 'updated_time',
        ],
        'EXCHANGE_TOKEN': True,
        'LOCALE_FUNC': 'path.to.callable',
        'VERIFIED_EMAIL': False,
        'VERSION': 'v2.5',
    }
}

REST_AUTH_REGISTER_SERIALIZERS = {
    'REGISTER_SERIALIZER': 'heartface.apps.auth.serializers.CustomRegisterSerializer'
}

REST_AUTH_SERIALIZERS = {
    'TOKEN_SERIALIZER': 'heartface.apps.auth.serializers.TokenSerializer',
    'PASSWORD_RESET_SERIALIZER': 'heartface.apps.auth.serializers.PasswordSerializer',
    'USER_DETAILS_SERIALIZER' : 'heartface.apps.auth.serializers.CustomUserDetailsSerializer',
}

# NOTE: this is not the unique user id (i.e. the email), but a (display) name for the user.
#   See http://django-allauth.readthedocs.io/en/latest/advanced.html#custom-user-models
# ACCOUNT_USER_MODEL_USERNAME_FIELD = 'first_name'
SOCIALACCOUNT_ADAPTER = 'heartface.apps.auth.adapters.SocialAccountAdapter'
ACCOUNT_ADAPTER = 'heartface.apps.auth.adapters.AccountAdapter'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True


USER_AGENTS_CACHE = 'default'

EMAIL_CONFIRM_REDIRECT = {
    'ios': 'heartface://email-confirmed',
    'android': 'heartface://email-confirmed',
    'desktop': '/'
}

STRIPE_TEST_PUBLIC_KEY = "xxxxxxxxxxxxxxxxxxxxxxx"
STRIPE_TEST_SECRET_KEY = "xxxxxxxxxxxxxxxxxxxxxxxx"


ONESIGNAL_REST_API_KEY = os.environ.get('ONESIGNAL_REST_API_KEY')
ONESIGNAL_AUTH_KEY = os.environ.get('ONESIGNAL_AUTH_KEY')
ONESIGNAL_APP_ID = os.environ.get('ONESIGNAL_APP_ID')

CDN_FTP = 'ftp10.pushrcdn.com'
CDN_USERNAME = '206'
CDN_PASSWORD = 'QRCaHMEH'
CDN_VIDEO_UPLOAD_PATH = '/media/upload/'
CDN_FILES_BASE_URL = 'https://ticker.heartface.io:8138/media/'
CDN_VIDEO_ROOT = '/video/'
CDN_COVER_PICTURE_ROOT = '/thumb/'
# Without the dot
CDN_COVER_PICTURE_EXTENSION = 'jpg'
CDN_VIDEO_EXTENSION = 'mp4'

CELERY_BROKER_URL = BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'

DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024

ELASTIC_URL = 'http://127.0.0.1:9200/'
DEFAULT_FROM_EMAIL = 'noreply@heartface.io'
DEFAULT_CONFIRMATION_FROM_EMAIL = 'hello@heartface.io'
DEFAULT_ORDERS_FROM_EMAIL = 'orders@heartface.io'
DEFAULT_ADMIN_EMAIL = 'orders-admin@heartface.io'

# Whether to use https urls in Elastic serialized models. (We want this by default.)
ELASTIC_STORE_URLS_AS_HTTPS=True

# The sensitivity for trending items to avoid false positives for unpopular
TRENDING_THRESHOLD = 10
#  How many top trending items to allow
TRENDING_LIMIT = 5

# Relative to STATIC_URL. Get full path in view using django.templatetags.static.static(DEFAULT_USER_AVATAR)
DEFAULT_USER_AVATAR = 'img/LogoBig.png'
DISABLED_USER_AVATAR = DEFAULT_USER_AVATAR
PRODUCT_PLACEHOLDER_IMAGE = 'img/product_placeholder.png'

VERSION = '?'

FILE_UPLOAD_PERMISSIONS = 0o644

# http://www.helios825.org/url-parameters.php
MARKETPLACES = [{'name': 'eBay',
                 'marketplace_id': 'ebay',
                 'logo': 'static/img/ebay_logo.png',
                 'search_url_template': 'https://www.ebay.co.uk/sch/i.html?_nkw=%s',
                 'affil_url_template': ('https://rover.ebay.com/rover/1/710-53481-19255-0/1'
                                        '?icep_id=114&ipn=icep&toolid=20004&campid=5338317961&mpre=%s')},
                ]

UNPUBLISHED_VIDEO_RETAIN_WINDOW = timedelta(hours=24)  # Keep unpublished vids for...


SUPPLIERS = ['Offspring', 'Schuh', 'Footasylum', 'Sports Direct', 'Vans',
             'New Balance', 'Timberland', 'Adidas', 'Urban Outfitters',
             'Urban Industry', 'Nike', 'Foot Locker', 'eBay', 'StockX',
             'End Clothing', 'Reebok', 'Footpatrol', 'Consortium',
             'Kickz', 'Size', 'JDSports', 'Spartoo', 'Kickgame', 'Fruugo',
             'AA Sports', 'Keller Sports', 'Very', 'Zalando', 'Asos'
             ]

LAST_SCRAPED_TIMESTAMP_WINDOW = timedelta(hours=3)

# settings for Scraper Image Pipeline
IMAGES_STORE = os.path.join(MEDIA_ROOT, 'scrapy_images')

# 30 days of delay for images expiration
IMAGES_EXPIRES = 30

IMAGES_THUMBS = {
    'small': (50, 50),
    'big': (270, 270),
}

BUNNY_CDN_PATH_PREFIX = 'images/'
BUNNY_CDN_ACCESS_KEY = '<overwrite_in_env_settings>'
BUNNY_CDN_STORAGE_NAME = '<overwrite_in_env_settings>'
BUNNY_CDN_BASE_URL = 'https://storage.bunnycdn.com'

POSTMAN_API_KEY = ''

# For analytics, what do we consider long/short videos
LONG_VIDEO_DURATION_SECONDS = 1200
SHORT_VIDEO_DURATION_SECONDS = 240

# Sendgrid
SENDGRID_VIDEO_LIKE_UNSUB_GROUP_ID = '<replace_me>'
SENDGRID_VIDEO_COMMENT_UNSUB_GROUP_ID = '<replace_me>'
SENDGRID_FOLLOW_UNSUB_GROUP_ID = '<replace_me>'
# Cf https://sendgrid.com/dynamic_templates (use handlebars syntax for dynamic
# context variables)
SENDGRID_VIDEO_LIKES_TEMPLATE_ID= ''
SENDGRID_VIDEO_COMMENT_TEMPLATE_ID= ''
SENDGRID_FOLLOW_TEMPLATE_ID= ''
SENDGRID_NOTIFICATIONS_EMAIL = "notifications@heartface.io"
