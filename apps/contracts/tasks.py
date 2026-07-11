from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_contract_expiry(self):
    """Notifie les agents et propriétaires 30 jours avant expiration du contrat"""
    from apps.contracts.models import AgentOwnerContract
    from apps.notifications.utils import notify

    today = timezone.now().date()
    expiry_alert_date = today + timedelta(days=30)

    expiring = AgentOwnerContract.objects.filter(
        status='active',
        end_date=expiry_alert_date
    )

    for contract in expiring:
        notify(
            user=contract.agent,
            notification_type='system',
            title="Contrat bientôt expiré",
            body=f"Votre contrat avec {contract.owner.get_full_name()} expire dans 30 jours.",
        )
        notify(
            user=contract.owner,
            notification_type='system',
            title="Contrat bientôt expiré",
            body=f"Votre contrat avec l'agent {contract.agent.get_full_name()} expire dans 30 jours.",
        )
        logger.info(f"[CELERY] Alerte expiration contrat: {contract.agent.get_full_name()} ↔ {contract.owner.get_full_name()}")

    logger.info("[CELERY] check_contract_expiry terminé ✅")


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def expire_old_contracts(self):
    """Marque automatiquement les contrats expirés"""
    try:
        from apps.contracts.models import AgentOwnerContract
        today = timezone.now().date()
        expired = AgentOwnerContract.objects.filter(
            status='active',
            end_date__lt=today
        )
        count = expired.update(status='expired')
        logger.info(f"[CELERY] {count} contrats expirés automatiquement")
    except Exception as exc:
        raise self.retry(exc=exc)
