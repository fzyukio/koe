from decouple import Csv

from .base import *  # noqa

INSTALLED_APPS += ['corsheaders']
MIDDLEWARE += ['corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware']

CORS_ORIGIN_ALLOW_ALL = True

DEBUG = False

SECRET_KEY = config('SECRET_KEY')

# DATABASES = {
#     'default': config('DATABASE_URL', cast=db_url),
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'koe.db'),
    }
}

DATABASES['default']['ATOMIC_REQUESTS'] = True

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

# User uploaded content
MEDIA_URL = '/user_data/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'user_data')

_email_config = config('EMAIL_CONFIG')
email_host, email_user, email_pass, email_port = _email_config.split(':', 3)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = email_host
EMAIL_HOST_USER = email_user
EMAIL_HOST_PASSWORD = email_pass
EMAIL_TIMEOUT = 10  # hopefully this is enough...
EMAIL_PORT = email_port
EMAIL_USE_TLS = True

SERVER_EMAIL = config('FROM_EMAIL')

# Security
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'http')
# SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = ['fa.io.ac.nz', 'farmassistant.co.nz', 'www.farmassistant.co.nz']

# Webpack
WEBPACK_LOADER['DEFAULT']['CACHE'] = True

# Celery
CELERY_BROKER_URL = config('REDIS_URL')
CELERY_RESULT_BACKEND = config('REDIS_URL')
CELERY_SEND_TASK_ERROR_EMAILS = True

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
    'APP_ID': 'a6e0d3f1d7',
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
