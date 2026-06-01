import os
from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

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

# ===================================
# BASE DE DONNÉES avec Connection Pooling
# ===================================
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='intelya_db'),
        'USER': config('DB_USER', default='intelya_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 600,  # Garder les connexions 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c default_transaction_isolation=read\ committed',
        },
    }
}

# ===================================
# CACHE Redis avec fallback gracieux
# ===================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'MAX_CONNECTIONS': 1000,
            'IGNORE_EXCEPTIONS': True,  # Si Redis down, utilise le cache mémoire
        },
        'KEY_PREFIX': 'intelya',
        'TIMEOUT': 300,
    }
}

# ===================================
# CELERY
# ===================================
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Douala'
CELERY_TASK_ACKS_LATE = True  # Confirme seulement après succès
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes max par tâche
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_DEFAULT_RETRY_DELAY = 60  # Retry après 60 secondes

# ===================================
# CHANNELS WebSocket
# ===================================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://localhost:6379/0')],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# ===================================
# REST FRAMEWORK
# ===================================
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
    # Throttling granulaire
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/hour',
        'user': '500/hour',
        'auth': '10/minute',
        'payments': '20/hour',
        'uploads': '30/hour',
        'search': '200/hour',
    },
}

# ===================================
# JWT
# ===================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # Réduit à 30min
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ===================================
# SWAGGER
# ===================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'INTELYA HAVEN API',
    'DESCRIPTION': 'API complète de la plateforme immobilière INTELYA HAVEN.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ===================================
# CORS
# ===================================
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
]
CORS_ALLOW_CREDENTIALS = True

# ===================================
# AUTH
# ===================================
AUTH_USER_MODEL = 'users.User'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

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
}

# ===================================
# STOCKAGE S3
# ===================================
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='intelya-haven-storage')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='eu-west-1')
AWS_DEFAULT_ACL = 'private'
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}

# ===================================
# FICHIERS
# ===================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ===================================
# EMAIL
# ===================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='INTELYA HAVEN <noreply@intelya-haven.com>')

# ===================================
# INTERNATIONALISATION
# ===================================
LANGUAGE_CODE = 'fr-cm'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True
LANGUAGES = [('fr', 'Français'), ('en', 'English')]

# ===================================
# SÉCURITÉ UPLOAD
# ===================================
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100

# ===================================
# PARAMÈTRES PLATEFORME
# ===================================

# ===== MODE GRATUIT (Phase de lancement) =====
# Mettre FREE_MODE=True dans .env pour désactiver toutes les commissions
FREE_MODE                    = config('FREE_MODE', default=True, cast=bool)
PLATFORM_COMMISSION_PERCENT  = 0 if FREE_MODE else config('PLATFORM_COMMISSION_PERCENT', default=2, cast=float)
BOOST_ENABLED                = not FREE_MODE
VISIT_FEE_ENABLED            = not FREE_MODE

PLATFORM_NAME = 'INTELYA HAVEN'
PLATFORM_CURRENCY = 'FCFA'
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)
OTP_EXPIRY_MINUTES = config('OTP_EXPIRY_MINUTES', default=15, cast=int)
VISIT_GPS_RADIUS_METERS = config('VISIT_GPS_RADIUS_METERS', default=200, cast=int)
VISIT_CONFIRMATION_HOURS = config('VISIT_CONFIRMATION_HOURS', default=24, cast=int)
LEASE_RENEWAL_PERCENT = config('LEASE_RENEWAL_PERCENT', default=83, cast=int)
DEBT_GRACE_DAYS_ALERT = config('DEBT_GRACE_DAYS_ALERT', default=3, cast=int)
DEBT_GRACE_DAYS_CLAIM = config('DEBT_GRACE_DAYS_CLAIM', default=7, cast=int)
DEBT_GRACE_DAYS_ADMIN = config('DEBT_GRACE_DAYS_ADMIN', default=15, cast=int)
DEBT_GRACE_DAYS_BLOCK = config('DEBT_GRACE_DAYS_BLOCK', default=30, cast=int)

FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='firebase-credentials.json')
SMILE_IDENTITY_API_KEY = config('SMILE_IDENTITY_API_KEY', default='')
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_API_URL = config('SMS_API_URL', default='')
SMS_SENDER_NAME = config('SMS_SENDER_NAME', default='INTELYA')
ORANGE_MONEY_API_KEY = config('ORANGE_MONEY_API_KEY', default='')
ORANGE_MONEY_API_URL = config('ORANGE_MONEY_API_URL', default='')
MTN_MOMO_API_KEY = config('MTN_MOMO_API_KEY', default='')
MTN_MOMO_API_URL = config('MTN_MOMO_API_URL', default='')
BANK_API_KEY = config('BANK_API_KEY', default='')
BANK_API_URL = config('BANK_API_URL', default='')
CAMPAY_USERNAME = config('CAMPAY_USERNAME', default='')
CAMPAY_PASSWORD = config('CAMPAY_PASSWORD', default='')
CAMPAY_WEBHOOK_SECRET = config('CAMPAY_WEBHOOK_SECRET', default='')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================================
# LOGGING STRUCTURÉ
# ===================================
import logging.handlers
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
        'audit':   {'format': '{asctime} AUDIT {message}', 'style': '{'},
    },
    'handlers': {
        'console':    {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
        'audit_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs/audit.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'audit',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs/errors.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'intelya.audit': {'handlers': ['console', 'audit_file'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['error_file'], 'level': 'ERROR', 'propagate': False},
        '': {'handlers': ['console'], 'level': 'WARNING'},
    },
}

# ===== CELERY BEAT SCHEDULE =====
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Vérifier loyers — tous les jours à 8h00
    'check-rent-payments': {
        'task': 'apps.leases.tasks.check_rent_payments',
        'schedule': crontab(hour=8, minute=0),
    },
    # Renouvellement baux — tous les jours à 9h00
    'check-lease-renewals': {
        'task': 'apps.leases.tasks.check_lease_renewals',
        'schedule': crontab(hour=9, minute=0),
    },
    # Blocage impayés — tous les jours à 10h00
    'block-unpaid-clients': {
        'task': 'apps.leases.tasks.block_unpaid_clients',
        'schedule': crontab(hour=10, minute=0),
    },
    # Expiration contrats — tous les jours à 7h00
    'check-contract-expiry': {
        'task': 'apps.contracts.tasks.check_contract_expiry',
        'schedule': crontab(hour=7, minute=0),
    },
    # Expirer vieux contrats — tous les jours à 7h30
    'expire-old-contracts': {
        'task': 'apps.contracts.tasks.expire_old_contracts',
        'schedule': crontab(hour=7, minute=30),
    },
    # Libération escrow — toutes les heures
    'auto-release-escrow': {
        'task': 'apps.payments.tasks.auto_release_escrow',
        'schedule': crontab(minute=0),
    },
    # Expiration boosts — tous les jours à 6h00
    'check-boost-expiry': {
        'task': 'apps.boost.tasks.check_boost_expiry',
        'schedule': crontab(hour=6, minute=0),
    },
    # Rapports mensuels — 1er de chaque mois à 6h00
    'monthly-reports': {
        'task': 'apps.leases.tasks.generate_monthly_reports',
        'schedule': crontab(hour=6, minute=0, day_of_month=1),
    },
}
