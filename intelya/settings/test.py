from .development import *

# ===== DÉSACTIVER AXES COMPLÈTEMENT EN TEST =====
AXES_ENABLED = False
AXES_FAILURE_LIMIT = 99999
AXES_COOLOFF_TIME = None
AXES_LOCKOUT_CALLABLE = None

# Retirer AxesMiddleware et AxesBackend
MIDDLEWARE = [m for m in MIDDLEWARE if 'axes' not in m.lower()]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Désactiver throttling
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '99999/hour',
        'user': '99999/hour',
        'auth': '99999/minute',
        'payments': '99999/hour',
        'uploads': '99999/hour',
        'search': '99999/hour',
    },
}

# Email en mémoire pour les tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Désactiver Cachalot en test
CACHALOT_ENABLED = False

# Permettre testserver pour les tests
ALLOWED_HOSTS = ['*', 'testserver', 'localhost', '127.0.0.1']

# Executer les taches Celery en synchrone, dans le process de test --
# aucun broker Redis n'est disponible en environnement de test, et rien
# ne doit dependre d'un worker externe pour que les tests soient fiables.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
