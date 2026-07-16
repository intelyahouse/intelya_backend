from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_bulk_push_task(self, user_ids, title, body, data=None):
    """Envoie des notifications push en masse"""
    try:
        from django.contrib.auth import get_user_model
        from apps.users.models import UserDevice
        User = get_user_model()

        tokens = list(
            UserDevice.objects.filter(
                user_id__in=user_ids,
                is_active=True
            ).values_list('device_token', flat=True)
        )

        if tokens:
            from core.firebase import send_push_to_multiple
            send_push_to_multiple(tokens, title, body, data or {})
            logger.info(f"[PUSH BULK] {len(tokens)} notifications envoyées")
    except Exception as exc:
        raise self.retry(exc=exc)
