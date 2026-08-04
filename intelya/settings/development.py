
# INTELYA HAVEN - Settings Development

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Email en développement — affiche dans la console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# CORS en développement — tout autoriser
CORS_ALLOW_ALL_ORIGINS = True

# Swagger visible en développement
SPECTACULAR_SETTINGS['SERVERS'] = [
    {'url': 'http://localhost:8000', 'description': 'Serveur de développement'},
]

# Logs SQL en développement
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'intelya': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}

# Désactiver throttling en tests
import sys
if 'pytest' in sys.modules or 'test' in sys.argv:
    REST_FRAMEWORK = {
        **REST_FRAMEWORK,
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {},
    }

# Désactivé en dev pour faciliter les tests (reste actif en production)
RATELIMIT_ENABLE = False
