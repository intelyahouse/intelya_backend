from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def remind_pending_validations(self):
    """Demandes agent/proprietaire en attente depuis plus de 48h --
    rappelle les admins une seule fois par demande (validation_reminder_sent),
    pour qu'aucune demande ne reste oubliee indefiniment."""
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.utils import notify_bulk
        User = get_user_model()

        stale = User.objects.filter(
            validation_status='pending',
            role__in=['agent', 'owner'],
            role_requested_at__lte=timezone.now() - timedelta(hours=48),
            validation_reminder_sent=False,
        )
        count = stale.count()
        if count:
            admins = User.objects.filter(role='admin', is_active=True)
            notify_bulk(
                admins, 'system', "Demandes de validation en attente depuis 48h",
                f"{count} demande(s) agent/propriétaire en attente depuis plus de 48h — merci de traiter."
            )
            stale.update(validation_reminder_sent=True)
        logger.info(f"[CELERY] remind_pending_validations : {count} rappel(s) envoye(s)")

    except Exception as exc:
        logger.error(f"[CELERY] remind_pending_validations échoué: {exc}")
        raise self.retry(exc=exc)
