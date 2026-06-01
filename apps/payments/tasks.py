from celery import shared_task
import logging
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def auto_release_escrow(self):
    try:
        from apps.payments.models import Escrow
        from apps.visits.models import VisitRequest
        from django.utils import timezone
        from django.db import transaction

        now = timezone.now()
        to_release = Escrow.objects.filter(status='held', release_after__lte=now).select_related('transaction')

        for escrow in to_release:
            try:
                with transaction.atomic():
                    escrow.status = 'released'
                    escrow.released_at = now
                    escrow.save()
                    if escrow.transaction.related_visit_id:
                        VisitRequest.objects.filter(
                            id=escrow.transaction.related_visit_id, status='scheduled'
                        ).update(status='completed', agent_confirmed=True)
                    logger.info(f"[CELERY] Escrow libéré: {escrow.amount} FCFA")
            except Exception as e:
                logger.error(f"[CELERY] Erreur escrow {escrow.id}: {e}")

    except Exception as exc:
        raise self.retry(exc=exc)
