from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def _agency_members(lease):
    """Tous les agents de l'agence gestionnaire du bail -- si l'un est
    absent, un collegue voit quand meme l'alerte. Retombe sur l'agent
    assigne seul si le bail n'a exceptionnellement pas d'agence."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if lease.agency_id:
        return list(User.objects.filter(agent_profile__agency_id=lease.agency_id))
    return [lease.agent] if lease.agent_id else []


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_rent_payments(self):
    """Vérifie les loyers en retard — retry automatique si échec"""
    try:
        from apps.leases.models import RentPayment
        from apps.notifications.utils import notify_rent_reminder, notify, notify_bulk
        from apps.notifications.services.sms import sms_service

        today = timezone.now().date()

        # J-5
        due_soon = RentPayment.objects.filter(
            status='pending', due_date=today + timedelta(days=5), alert_sent_minus5=False
        ).select_related('tenant', 'lease__agent')

        for payment in due_soon:
            try:
                notify_rent_reminder(payment.tenant, payment.amount, payment.due_date)
                sms_service.send_rent_reminder(payment.tenant.phone, f"{payment.amount} FCFA", str(payment.due_date))
                payment.alert_sent_minus5 = True
                payment.save(update_fields=['alert_sent_minus5'])
            except Exception as e:
                logger.error(f"[CELERY] Erreur rappel J-5 {payment.tenant.email}: {e}")

        # J+3
        late_3 = RentPayment.objects.filter(
            status='pending', due_date=today - timedelta(days=3), alert_sent_plus3=False
        ).select_related('tenant', 'lease__agency')

        for payment in late_3:
            try:
                payment.status = 'late'
                payment.alert_sent_plus3 = True
                payment.save(update_fields=['status', 'alert_sent_plus3'])
                members = _agency_members(payment.lease)
                if members:
                    notify_bulk(
                        members, 'rent_late', "Loyer en retard",
                        f"{payment.tenant.get_full_name()} n'a pas payé son loyer de {payment.amount} FCFA",
                        {'payment_id': str(payment.id)}
                    )
            except Exception as e:
                logger.error(f"[CELERY] Erreur alerte J+3: {e}")

        # J+7 — l'agence ET le proprietaire (interet financier direct)
        late_7 = RentPayment.objects.filter(
            status='late', due_date=today - timedelta(days=7), alert_sent_plus7=False
        ).select_related('tenant', 'lease__agency', 'lease__owner', 'lease__rental_property')

        for payment in late_7:
            try:
                payment.alert_sent_plus7 = True
                payment.save(update_fields=['alert_sent_plus7'])
                members = _agency_members(payment.lease)
                if members:
                    notify_bulk(
                        members, 'rent_late', "Action requise — Loyer J+7",
                        f"{payment.tenant.get_full_name()} doit {payment.amount} FCFA depuis 7 jours",
                        {'payment_id': str(payment.id)}
                    )
                if payment.lease.owner_id:
                    notify(
                        payment.lease.owner, 'rent_late', "Votre locataire n'a pas payé — J+7",
                        f"{payment.tenant.get_full_name()} doit {payment.amount} FCFA depuis 7 jours pour {payment.lease.rental_property.title}.",
                        {'payment_id': str(payment.id)}
                    )
            except Exception as e:
                logger.error(f"[CELERY] Erreur alerte J+7: {e}")

        # J+30 — alerte critique (le blocage est gere par block_unpaid_clients), email en plus
        late_30 = RentPayment.objects.filter(
            status='late', due_date__lte=today - timedelta(days=30), alert_sent_plus30=False
        ).select_related('tenant', 'lease__agency', 'lease__owner')

        for payment in late_30:
            try:
                payment.alert_sent_plus30 = True
                payment.save(update_fields=['alert_sent_plus30'])
                members = _agency_members(payment.lease)
                if members:
                    notify_bulk(
                        members, 'rent_late', "Impayé critique J+30",
                        f"{payment.tenant.get_full_name()} n'a pas payé depuis 30 jours. Accès bloqué.",
                        {'payment_id': str(payment.id)}
                    )
                if payment.lease.owner_id:
                    notify(
                        payment.lease.owner, 'rent_late', "Impayé critique J+30",
                        f"{payment.tenant.get_full_name()} n'a pas payé son loyer de {payment.amount} FCFA depuis 30 jours. Son accès à INTELYA HAVEN a été bloqué.",
                        {'payment_id': str(payment.id)}, send_email=True
                    )
            except Exception as e:
                logger.error(f"[CELERY] Erreur alerte J+30: {e}")

        logger.info("[CELERY] check_rent_payments OK")

    except Exception as exc:
        logger.error(f"[CELERY] check_rent_payments échoué: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_lease_renewals(self):
    try:
        from apps.contracts.models import LeaseContract
        from apps.notifications.utils import notify, notify_bulk

        today = timezone.now().date()
        active_leases = LeaseContract.objects.filter(
            status='active', renewal_notified=False
        ).select_related('tenant', 'agent', 'agency', 'owner', 'rental_property')

        for lease in active_leases:
            try:
                renewal_date = lease.get_renewal_notification_date()
                if today >= renewal_date:
                    notify(lease.tenant, 'lease_renewal', "Bail bientôt expiré",
                           f"Votre bail pour {lease.rental_property.title} expire le {lease.end_date}.",
                           {'lease_id': str(lease.id)})
                    if lease.owner_id:
                        notify(lease.owner, 'lease_renewal', "Bail de votre locataire bientôt expiré",
                               f"Le bail de {lease.tenant.get_full_name()} pour {lease.rental_property.title} expire le {lease.end_date}.",
                               {'lease_id': str(lease.id)})
                    members = _agency_members(lease)
                    if members:
                        notify_bulk(
                            members, 'lease_renewal', "Bail client expiré",
                            f"Le bail de {lease.tenant.get_full_name()} expire le {lease.end_date}.",
                            {'lease_id': str(lease.id)}
                        )
                    lease.renewal_notified = True
                    lease.renewal_notified_at = timezone.now()
                    lease.save(update_fields=['renewal_notified', 'renewal_notified_at'])
            except Exception as e:
                logger.error(f"[CELERY] Erreur renewal {lease.id}: {e}")

        logger.info("[CELERY] check_lease_renewals OK")

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def block_unpaid_clients(self):
    try:
        from apps.leases.models import RentPayment
        today = timezone.now().date()
        overdue = RentPayment.objects.filter(
            status='late', due_date__lte=today - timedelta(days=30)
        ).select_related('tenant')
        for payment in overdue:
            if not payment.tenant.is_blocked:
                payment.tenant.is_blocked = True
                payment.tenant.save(update_fields=['is_blocked'])
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def generate_monthly_reports(self):
    try:
        from apps.leases.models import RentPayment
        from apps.notifications.utils import notify
        last_month = timezone.now().replace(day=1) - timedelta(days=1)
        payments = RentPayment.objects.filter(
            status='paid', period_month=last_month.month, period_year=last_month.year
        ).select_related('tenant')
        for payment in payments:
            notify(payment.tenant, 'payment_success', "Reçu mensuel disponible",
                   f"Votre reçu de loyer {last_month.strftime('%B %Y')} est disponible.")
        logger.info(f"[CELERY] {payments.count()} reçus générés")
    except Exception as exc:
        raise self.retry(exc=exc)
