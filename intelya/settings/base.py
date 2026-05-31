
# INTELYA HAVEN - Settings Base

import os
from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')


# APPLICATIONS
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'storages',
    'channels',
    'django_extensions',
]

LOCAL_APPS = [
    'apps.users',
    'apps.agents',
    'apps.owners',
    'apps.properties',
    'apps.visits',
    'apps.contracts',
    'apps.leases',
    'apps.payments',
    'apps.messaging',
    'apps.notifications',
    'apps.reviews',
    'apps.disputes',
    'apps.boost',
    'apps.referrals',
    'core',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# MIDDLEWARE
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'intelya.urls'


# TEMPLATES
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'intelya.wsgi.application'
ASGI_APPLICATION = 'intelya.asgi.application'


# BASE DE DONNÉES PostgreSQL + PostGIS
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='intelya_db'),
        'USER': config('DB_USER', default='intelya_user'),
        'PASSWORD': config('DB_PASSWORD', default='intelya_password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}


# CACHE - Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}


# CELERY - Tâches asynchrones

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Douala'
CELERY_BEAT_SCHEDULE = {}


# CHANNELS - WebSocket (Chat temps réel)

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}

# JWT Authentication

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}


# SWAGGER - Documentation API
SPECTACULAR_SETTINGS = {
    'TITLE': 'INTELYA HAVEN API',
    'DESCRIPTION': '''
    API complète de la plateforme immobilière INTELYA HAVEN.
    
    ## Authentification
    Utilise JWT Bearer Token. Obtiens ton token via /api/auth/login/
    
    ## Rôles disponibles
    - **Admin** : Accès total
    - **Agent** : Gestion clients, biens, visites, contrats
    - **Propriétaire** : Gestion de ses biens et locataires  
    - **Client** : Recherche et location
    - **Locataire** : Gestion du bail actif
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'TAGS': [
        {'name': 'Auth', 'description': 'Authentification et gestion de compte'},
        {'name': 'Users', 'description': 'Gestion des utilisateurs'},
        {'name': 'Agents', 'description': 'Agents immobiliers'},
        {'name': 'Owners', 'description': 'Propriétaires'},
        {'name': 'Properties', 'description': 'Biens immobiliers'},
        {'name': 'Visits', 'description': 'Gestion des visites'},
        {'name': 'Contracts', 'description': 'Contrats et baux'},
        {'name': 'Leases', 'description': 'Gestion locative'},
        {'name': 'Payments', 'description': 'Paiements et transactions'},
        {'name': 'Messaging', 'description': 'Chat et messagerie'},
        {'name': 'Notifications', 'description': 'Notifications'},
        {'name': 'Reviews', 'description': 'Avis et notations'},
        {'name': 'Disputes', 'description': 'Litiges et signalements'},
        {'name': 'Boost', 'description': 'Système de boost agents'},
        {'name': 'Referrals', 'description': 'Parrainage'},
        {'name': 'Admin', 'description': 'Administration plateforme'},
    ],
}


# CORS - Autoriser le frontend
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
]
CORS_ALLOW_CREDENTIALS = True


# AUTH - Modèle utilisateur custom
AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


# ALLAUTH - Google et Apple OAuth
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret': config('GOOGLE_CLIENT_SECRET', default=''),
        }
    },
    'apple': {
        'APP': {
            'client_id': config('APPLE_CLIENT_ID', default=''),
            'secret': config('APPLE_TEAM_ID', default=''),
        }
    }
}


# STOCKAGE - AWS S3
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='intelya-haven-storage')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='eu-west-1')
AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default='')
AWS_DEFAULT_ACL = 'private'
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}


# FICHIERS STATIQUES ET MEDIA

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# EMAIL

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='INTELYA HAVEN <noreply@intelya-haven.com>')


# INTERNATIONALISATION

LANGUAGE_CODE = 'fr-cm'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True
LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
]


# PARAMÈTRES PLATEFORME
PLATFORM_COMMISSION_PERCENT = config('PLATFORM_COMMISSION_PERCENT', default=2, cast=float)
PLATFORM_NAME = config('PLATFORM_NAME', default='INTELYA HAVEN')
PLATFORM_CURRENCY = config('PLATFORM_CURRENCY', default='FCFA')
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

# Sécurité
MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)
OTP_EXPIRY_MINUTES = config('OTP_EXPIRY_MINUTES', default=15, cast=int)
VISIT_GPS_RADIUS_METERS = config('VISIT_GPS_RADIUS_METERS', default=200, cast=int)
VISIT_CONFIRMATION_HOURS = config('VISIT_CONFIRMATION_HOURS', default=24, cast=int)
LEASE_RENEWAL_PERCENT = config('LEASE_RENEWAL_PERCENT', default=83, cast=int)

# Gestion des dettes
DEBT_GRACE_DAYS_ALERT = config('DEBT_GRACE_DAYS_ALERT', default=3, cast=int)
DEBT_GRACE_DAYS_CLAIM = config('DEBT_GRACE_DAYS_CLAIM', default=7, cast=int)
DEBT_GRACE_DAYS_ADMIN = config('DEBT_GRACE_DAYS_ADMIN', default=15, cast=int)
DEBT_GRACE_DAYS_BLOCK = config('DEBT_GRACE_DAYS_BLOCK', default=30, cast=int)

# Firebase
FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='firebase-credentials.json')

# Smile Identity
SMILE_IDENTITY_API_KEY = config('SMILE_IDENTITY_API_KEY', default='')
SMILE_IDENTITY_PARTNER_ID = config('SMILE_IDENTITY_PARTNER_ID', default='')

# SMS
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_API_URL = config('SMS_API_URL', default='')
SMS_SENDER_NAME = config('SMS_SENDER_NAME', default='INTELYA')

# Paiements
ORANGE_MONEY_API_KEY = config('ORANGE_MONEY_API_KEY', default='')
ORANGE_MONEY_API_URL = config('ORANGE_MONEY_API_URL', default='')
MTN_MOMO_API_KEY = config('MTN_MOMO_API_KEY', default='')
MTN_MOMO_API_URL = config('MTN_MOMO_API_URL', default='')
BANK_API_KEY = config('BANK_API_KEY', default='')
BANK_API_URL = config('BANK_API_URL', default='')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# RATE LIMITING
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = True
