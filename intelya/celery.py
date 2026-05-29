# ===================================
# INTELYA HAVEN - Celery Configuration
# ===================================

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelya.settings')

app = Celery('intelya')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ===================================
# TÂCHES PÉRIODIQUES (Celery Beat)
# ===================================
app.conf.beat_schedule = {

    # Rappels loyers — vérifie chaque jour à 8h
    'check-rent-payments-daily': {
        'task': 'apps.leases.tasks.check_rent_payments',
        'schedule': crontab(hour=8, minute=0),
    },

    # Rappels renouvellement bail — vérifie chaque jour à 9h
    'check-lease-renewals-daily': {
        'task': 'apps.leases.tasks.check_lease_renewals',
        'schedule': crontab(hour=9, minute=0),
    },

    # Expiration boost agents — vérifie chaque heure
    'check-boost-expiry': {
        'task': 'apps.boost.tasks.check_boost_expiry',
        'schedule': crontab(minute=0),
    },

    # Expiration contrats — vérifie chaque jour à 10h
    'check-contract-expiry': {
        'task': 'apps.contracts.tasks.check_contract_expiry',
        'schedule': crontab(hour=10, minute=0),
    },

    # Libération escrow automatique après 24h — vérifie toutes les heures
    'auto-release-escrow': {
        'task': 'apps.payments.tasks.auto_release_escrow',
        'schedule': crontab(minute=30),
    },

    # Rapports mensuels — 1er de chaque mois à 7h
    'generate-monthly-reports': {
        'task': 'apps.leases.tasks.generate_monthly_reports',
        'schedule': crontab(hour=7, minute=0, day_of_month=1),
    },

    # Blocage clients impayés — vérifie chaque jour à 11h
    'block-unpaid-clients': {
        'task': 'apps.leases.tasks.block_unpaid_clients',
        'schedule': crontab(hour=11, minute=0),
    },
}

app.conf.timezone = 'Africa/Douala'
