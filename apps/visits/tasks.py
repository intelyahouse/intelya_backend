from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_visit_reminders(self):
    """Rappelle au client ET a l'agent une visite programmee pour le
    lendemain -- aucune tache periodique n'existait pour les visites,
    seule la notification immediate a la planification etait envoyee."""
    try:
        from apps.visits.models import VisitRequest
        from apps.notifications.utils import notify

        tomorrow = timezone.now().date() + timedelta(days=1)
        due = VisitRequest.objects.filter(
            status__in=['scheduled', 'confirmed'],
            scheduled_date=tomorrow,
            reminder_sent=False,
        ).select_related('client', 'agent', 'visit_property')

        count = 0
        for visit in due:
            try:
                time_label = visit.scheduled_time.strftime('%Hh%M') if visit.scheduled_time else "l'heure convenue"
                notify(
                    visit.client, 'visit_scheduled', "Rappel — Visite demain",
                    f"Votre visite de {visit.visit_property.title} est prévue demain à {time_label}.",
                    {'visit_id': str(visit.id)}
                )
                notify(
                    visit.agent, 'visit_scheduled', "Rappel — Visite demain",
                    f"Visite avec {visit.client.get_full_name()} pour {visit.visit_property.title} prévue demain à {time_label}.",
                    {'visit_id': str(visit.id)}
                )
                visit.reminder_sent = True
                visit.save(update_fields=['reminder_sent'])
                count += 1
            except Exception as e:
                logger.error(f"[CELERY] Erreur rappel visite {visit.id}: {e}")

        logger.info(f"[CELERY] send_visit_reminders : {count} rappel(s) envoye(s)")

    except Exception as exc:
        logger.error(f"[CELERY] send_visit_reminders échoué: {exc}")
        raise self.retry(exc=exc)
