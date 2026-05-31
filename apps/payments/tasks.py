from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def auto_release_escrow():
    """
    Libère automatiquement l'escrow après 24h si non contesté.
    La visite est considérée effectuée si le client ne conteste pas.
    """
    from apps.payments.models import Escrow
    from apps.visits.models import VisitRequest

    now = timezone.now()
    to_release = Escrow.objects.filter(
        status='held',
        release_after__lte=now
    ).select_related('transaction')

    for escrow in to_release:
        escrow.status     = 'released'
        escrow.released_at = now
        escrow.save()

        # Marquer la visite comme complétée
        if escrow.transaction.related_visit_id:
            VisitRequest.objects.filter(
                id=escrow.transaction.related_visit_id,
                status='scheduled'
            ).update(status='completed', agent_confirmed=True)

        logger.info(f"[CELERY] Escrow libéré: {escrow.amount} FCFA — {escrow.transaction.reference}")

    if to_release.count() > 0:
        logger.info(f"[CELERY] {to_release.count()} escrow(s) libéré(s) ✅")
