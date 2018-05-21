import sys
import datetime
import os
from json import JSONEncoder

import dj_database_url

from maintenance import config as envconf, base_dir_join

BASE_DIR = envconf['base_dir']


SITE_ID = 1

SECRET_KEY = envconf['secret_key']

DEBUG = envconf['debug']

ALLOWED_HOSTS = envconf['allowed_hosts']

ADMINS = (
    ('Admin', 'foo@example.com'),
)

AUTH_USER_MODEL = 'root.User'

INSTALLED_APPS = [
    'grappelli',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',
    'django_countries',
    'django_js_reverse',
    'webpack_loader',
    'widget_tweaks',
    'tz_detect',

    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail.core',

    'modelcluster',
    'taggit',

    'root',
    'koe',
    'cms'
]

MIDDLEWARE = [
    'wagtail.core.middleware.SiteMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tz_detect.middleware.TimezoneMiddleware',
    'root.exception_handlers.HandleBusinessExceptionMiddleware'
]

ROOT_URLCONF = 'koe.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [base_dir_join('templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

# User uploaded content
MEDIA_URL = '/user_data/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'user_data')

WSGI_APPLICATION = 'koe.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-nz'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATICFILES_DIRS = (
    base_dir_join('assets'),
)

# Webpack
WEBPACK_LOADER = {
    'DEFAULT': {
        'CACHE': False,  # on DEBUG should be False
        'BUNDLE_DIR_NAME': 'bundles/',  # must end with slash
        'STATS_FILE': base_dir_join('webpack-stats.json'),
        'POLL_INTERVAL': 0.1,
        'IGNORE': ['.+\.hot-update.js', '.+\.map']
    },
    'JQUERY': {
        'BUNDLE_DIR_NAME': 'bundles/',
        'STATS_FILE': 'jquery-webpack-stats.json',
    }
}

MAX_FILE_NAME_LENGTH = 20
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Redis cache
_cache_config = envconf.get('cache', None)
if _cache_config:
    CACHES = {
        'default': {
            'BACKEND': _cache_config['backend'],
            'LOCATION': _cache_config['location'],
            'OPTIONS': _cache_config['options']
        }
    }

LOGIN_URL = '/login'

# site configuration
SITE_URL = envconf['site_url']
SITE_URL_BARE = SITE_URL[:-1]
assert SITE_URL.endswith('/'), 'SITE_URL must have trailing /'

EMAIL_CONFIG = envconf['email_config']
if EMAIL_CONFIG == 'console':
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    FROM_EMAIL = ''
else:  # assume we have fully-specified smtp configuration
    email_host, email_user, email_pass, email_port = EMAIL_CONFIG.split(':', 3)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = email_host
    EMAIL_HOST_USER = email_user
    EMAIL_HOST_PASSWORD = email_pass
    EMAIL_TIMEOUT = 10  # hopefully this is enough...
    EMAIL_PORT = email_port
    EMAIL_USE_TLS = True
    FROM_EMAIL = envconf['from_email']

DATABASES = {
    'default': dj_database_url.parse(envconf['database_url'])
}

WAGTAIL_SITE_NAME = 'Koe'

JSONEncoder_olddefault = JSONEncoder.default


def JSONEncoder_newdefault(self, obj):
    """
    The original JSONEncoder doesn't handle datetime object.
    Replace it with this
    :param self:
    :param obj:
    :return: the JSONified string
    """
    if isinstance(obj, datetime.datetime):
        return obj.strftime(TIME_INPUT_FORMAT)
    elif isinstance(obj, datetime.date):
        return obj.strftime(DATE_INPUT_FORMAT)
    return JSONEncoder_olddefault(self, obj)


JSONEncoder.default = JSONEncoder_newdefault

AUDIO_COMPRESSED_FORMAT = 'mp4'

TZ_DETECT_COUNTRIES = ('NZ', 'AU', 'GB', 'US', 'CA', 'CN', 'JP', 'FR', 'DE')

CSRF_TRUSTED_ORIGINS = envconf['csrf_trusted_origin']

DATE_INPUT_FORMAT = '%Y-%m-%d'
TIME_INPUT_FORMAT = '%Y-%m-%d %H:%M:%S %z%Z'

# For local run:
if DEBUG:

    HOST = 'http://localhost:8000'

    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

    AUTH_PASSWORD_VALIDATORS = []  # allow easy passwords only on local

    # Logging
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(levelname)-8s [%(asctime)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
        },
        'loggers': {
            '': {
                'handlers': ['console'],
                'level': 'INFO'
            }
        }
    }

    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

    JS_REVERSE_JS_MINIFY = False

    PY3 = sys.version_info[0] == 3
    if PY3:
        import builtins
    else:
        import __builtin__ as builtins

    try:
        builtins.profile
    except AttributeError:
        builtins.profile = lambda x: x

        # For production run:
else:
    INSTALLED_APPS += ['corsheaders']
    MIDDLEWARE += ['corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware']

    CORS_ORIGIN_ALLOW_ALL = True

    DATABASES['default']['ATOMIC_REQUESTS'] = True

    # Security
    # SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'http')
    # SECURE_SSL_REDIRECT = True
    # SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_COOKIE_HTTPONLY = True

    # Webpack
    WEBPACK_LOADER['DEFAULT']['CACHE'] = True

    # Whitenoise
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    MIDDLEWARE.insert(  # insert WhiteNoiseMiddleware right after SecurityMiddleware
        MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
        'whitenoise.middleware.WhiteNoiseMiddleware')

    # django-log-request-id
    MIDDLEWARE.insert(  # insert RequestIDMiddleware on the top
        0, 'log_request_id.middleware.RequestIDMiddleware')

    LOG_REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
    LOG_REQUESTS = True

    # Opbeat
    INSTALLED_APPS += ['opbeat.contrib.django']
    OPBEAT = {
        'ORGANIZATION_ID': '07d57ec41f4442539ceaf70270d1b3a5',
        'APP_ID': '145395c333',
        'SECRET_TOKEN': '227d2d8537b77d3e50f452578efcf18eeafa387e',
    }
    MIDDLEWARE.insert(  # insert OpbeatAPMMiddleware on the top
        0, 'opbeat.contrib.django.middleware.OpbeatAPMMiddleware')

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'require_debug_false': {
                '()': 'django.utils.log.RequireDebugFalse'
            },
            'request_id': {
                '()': 'log_request_id.filters.RequestIDFilter'
            },
        },
        'formatters': {
            'standard': {
                'format': '%(levelname)-8s [%(asctime)s] [%(request_id)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'null': {
                'class': 'logging.NullHandler',
            },
            'mail_admins': {
                'level': 'ERROR',
                'class': 'django.utils.log.AdminEmailHandler',
                'filters': ['require_debug_false'],
            },
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'filters': ['request_id'],
                'formatter': 'standard',
            },
        },
        'loggers': {
            '': {
                'handlers': ['console'],
                'level': 'INFO'
            },
            'django.security.DisallowedHost': {
                'handlers': ['null'],
                'propagate': False,
            },
            'django.request': {
                'handlers': ['mail_admins'],
                'level': 'ERROR',
                'propagate': True,
            },
            'log_request_id.middleware': {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': False,
            },
        }
    }

    JS_REVERSE_EXCLUDE_NAMESPACES = ['admin']
