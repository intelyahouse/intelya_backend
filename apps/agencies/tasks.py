from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

INVITATION_EXPIRY_DAYS = 7


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def expire_stale_invitations(self):
    """Invitation d'agence sans reponse depuis plus de 7 jours -- expire
    automatiquement pour ne pas bloquer indefiniment l'invite (qui ne
    pouvait plus recevoir de nouvelle invitation tant que celle-ci restait
    'pending') ni laisser le gerant sans reponse."""
    try:
        from apps.agencies.models import AgencyInvitation
        from apps.notifications.utils import notify

        stale = AgencyInvitation.objects.filter(
            status='pending',
            created_at__lte=timezone.now() - timedelta(days=INVITATION_EXPIRY_DAYS),
        ).select_related('agency', 'invited_user', 'invited_by')

        count = 0
        for invitation in stale:
            try:
                invitation.status = 'expired'
                invitation.responded_at = timezone.now()
                invitation.save(update_fields=['status', 'responded_at'])

                notify(
                    invitation.invited_user, 'agency_invitation', "Invitation expirée",
                    f"L'invitation de l'agence {invitation.agency.name} a expiré (sans réponse après {INVITATION_EXPIRY_DAYS} jours).",
                    {'invitation_id': str(invitation.id)}
                )
                notify(
                    invitation.invited_by, 'agency_invitation', "Invitation expirée",
                    f"Votre invitation à {invitation.invited_user.get_full_name()} a expiré sans réponse.",
                    {'invitation_id': str(invitation.id)}
                )
                count += 1
            except Exception as e:
                logger.error(f"[CELERY] Erreur expiration invitation {invitation.id}: {e}")

        logger.info(f"[CELERY] expire_stale_invitations : {count} invitation(s) expiree(s)")

    except Exception as exc:
        logger.error(f"[CELERY] expire_stale_invitations échoué: {exc}")
        raise self.retry(exc=exc)
