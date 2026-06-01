from celery import shared_task
import logging
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_boost_expiry(self):
    try:
        from apps.boost.models import Boost
        from apps.notifications.utils import notify_boost_expired
        from django.utils import timezone

        expired = Boost.objects.filter(is_active=True, end_date__lte=timezone.now()).select_related('agent')
        for boost in expired:
            boost.is_active = False
            boost.save(update_fields=['is_active'])
            notify_boost_expired(boost.agent)
        if expired.count() > 0:
            logger.info(f"[CELERY] {expired.count()} boost(s) expirés")
    except Exception as exc:
        raise self.retry(exc=exc)
