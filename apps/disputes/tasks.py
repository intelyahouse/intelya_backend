from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def escalate_stale_disputes(self):
    """Litiges ouverts depuis plus de 48h sans reponse du defendeur --
    passent en examen pour que l'admin puisse arbitrer sans attendre
    indefiniment une reponse qui ne viendra pas."""
    try:
        from apps.disputes.models import Dispute
        from django.contrib.auth import get_user_model
        from apps.notifications.utils import notify_bulk
        User = get_user_model()

        stale = Dispute.objects.filter(
            status='open', created_at__lte=timezone.now() - timedelta(hours=48)
        )
        count = stale.count()
        if count:
            stale.update(status='reviewing')
            admins = User.objects.filter(role='admin', is_active=True)
            notify_bulk(
                admins, 'dispute_opened', "Litiges sans réponse — arbitrage requis",
                f"{count} litige(s) sans réponse du défendeur après 48h, prêt(s) pour arbitrage."
            )
        logger.info(f"[CELERY] escalate_stale_disputes : {count} litige(s) escalade(s)")

    except Exception as exc:
        logger.error(f"[CELERY] escalate_stale_disputes échoué: {exc}")
        raise self.retry(exc=exc)
