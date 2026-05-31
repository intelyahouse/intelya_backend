from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_boost_expiry():
    """Désactive les boosts expirés et notifie les agents"""
    from apps.boost.models import Boost
    from apps.notifications.utils import notify_boost_expired

    expired = Boost.objects.filter(
        is_active=True,
        end_date__lte=timezone.now()
    )

    for boost in expired:
        boost.is_active = False
        boost.save(update_fields=['is_active'])
        notify_boost_expired(boost.agent)
        logger.info(f"[CELERY] Boost expiré: {boost.agent.get_full_name()} — {boost.level}")

    if expired.count() > 0:
        logger.info(f"[CELERY] {expired.count()} boost(s) désactivé(s) ✅")
