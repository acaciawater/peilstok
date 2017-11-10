"""
Django settings for peil project.

Generated by 'django-admin startproject' using Django 1.11.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['.phzdmeet.nl','.acaciadata.com','localhost']

# Application definition

INSTALLED_APPS = [
    'polymorphic',
    'django.contrib.contenttypes',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'sorl.thumbnail',
    'tastypie',
    'bootstrap3',
    'peil.apps.PeilConfig',
    'django_extensions', # for debugging ssl with runserver_plus
    'django_redis',
    'debug_toolbar',
]

MIDDLEWARE = [
    #'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    #'django.middleware.cache.FetchFromCacheMiddleware',
]

ROOT_URLCONF = 'peil.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'peil.wsgi.application'


# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'nl-nl'

TIME_ZONE = 'Europe/Amsterdam'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# debug toolbar
INTERNAL_IPS = '127.0.0.1'

# sorl.thumbnail
THUMBNAIL_KVSTORE = 'sorl.thumbnail.kvstores.redis_kvstore.KVStore'
TEMPLATE_DEBUG = True

# tastypie
TASTYPIE_DEFAULT_FORMATS = ['json']

# registration
REGISTRATION_OPEN = False
REGISTRATION_SALT = 'Peilstok13579'
LOGIN_REDIRECT_URL = '/'
ACCOUNT_ACTIVATION_DAYS = 7

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Media files (photos)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

GNSS_URL = '/gnss/'
GNSS_ROOT = os.path.join(BASE_DIR, 'media','gnss')

# send updates to Orion Context broker?
USE_ORION = True
ORION_URL = 'http://fiware.acaciadata.com:1026/v2/'

# Logging
LOGGING_ROOT = os.path.join(BASE_DIR, 'logs')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGGING_ROOT, 'peil.log'),
            'when': 'D',
            'interval': 1, # every day a new file
            'backupCount': 0,
            'formatter': 'default'
        },
        'fiware': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGGING_ROOT, 'fiware.log'),
            'when': 'D',
            'interval': 1, # every day a new file
            'backupCount': 0,
            'formatter': 'default'
        },
        'django': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGGING_ROOT, 'django.log'),
            'when': 'D',
            'interval': 1, # every day a new file
            'backupCount': 0,
        },
        'console':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        }
    },
    'formatters': {
        'default': {
            'format': '%(levelname)s %(asctime)s %(name)s: %(message)s'
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['django'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'peil': {
            'handlers': ['file',],
            'level': 'DEBUG',
            'propagate': True,
        },
        'peil.management.commands': {
            'handlers': ['console',],
            'level': 'DEBUG',
            'propagate': True,
        },
        'peil.fiware': {
            'handlers': ['fiware',],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

from secrets import *