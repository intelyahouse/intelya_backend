"""
Tâches Celery automatiques pour la gestion locative.
Lancées automatiquement selon le calendrier dans intelya/celery.py
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_rent_payments():
    """
    Vérifie chaque jour les loyers en retard.
    Lance les alertes progressives J-5, J+3, J+7, J+15, J+30
    """
    from apps.leases.models import RentPayment
    from apps.notifications.utils import notify_rent_reminder, notify_rent_late
    from apps.notifications.services.sms import sms_service

    today = timezone.now().date()

    # J-5 — Rappel avant échéance
    due_soon = RentPayment.objects.filter(
        status='pending',
        due_date=today + timedelta(days=5),
        alert_sent_minus5=False
    )
    for payment in due_soon:
        notify_rent_reminder(payment.tenant, payment.amount, payment.due_date)
        sms_service.send_rent_reminder(
            payment.tenant.phone,
            f"{payment.amount} FCFA",
            str(payment.due_date)
        )
        payment.alert_sent_minus5 = True
        payment.save(update_fields=['alert_sent_minus5'])
        logger.info(f"[CELERY] Rappel J-5 envoyé à {payment.tenant.get_full_name()}")

    # J+3 — Alerte agent
    late_3 = RentPayment.objects.filter(
        status='pending',
        due_date=today - timedelta(days=3),
        alert_sent_plus3=False
    )
    for payment in late_3:
        payment.status = 'late'
        payment.alert_sent_plus3 = True
        payment.save(update_fields=['status', 'alert_sent_plus3'])
        if payment.lease.agent:
            notify_rent_late(payment.lease.agent, payment.tenant.get_full_name(), payment.amount)
        logger.info(f"[CELERY] Alerte J+3 pour {payment.tenant.get_full_name()}")

    # J+7 — Question agent prolonger ou réclamer
    late_7 = RentPayment.objects.filter(
        status='late',
        due_date=today - timedelta(days=7),
        alert_sent_plus7=False
    )
    for payment in late_7:
        payment.alert_sent_plus7 = True
        payment.save(update_fields=['alert_sent_plus7'])
        if payment.lease.agent:
            from apps.notifications.utils import notify
            notify(
                user=payment.lease.agent,
                notification_type='rent_late',
                title="Action requise — Loyer en retard",
                body=f"{payment.tenant.get_full_name()} n'a pas payé depuis 7 jours. Prolonger ou réclamer ?",
                data={'payment_id': str(payment.id)}
            )
        logger.info(f"[CELERY] Alerte J+7 agent pour {payment.tenant.get_full_name()}")

    # J+15 — Alerte admin
    late_15 = RentPayment.objects.filter(
        status='late',
        due_date=today - timedelta(days=15),
        alert_sent_plus15=False
    )
    for payment in late_15:
        payment.alert_sent_plus15 = True
        payment.save(update_fields=['alert_sent_plus15'])
        logger.warning(f"[CELERY] ⚠️ Loyer J+15 non résolu — {payment.tenant.get_full_name()}")

    # J+30 — Blocage accès client
    late_30 = RentPayment.objects.filter(
        status='late',
        due_date=today - timedelta(days=30),
        alert_sent_plus30=False
    )
    for payment in late_30:
        payment.alert_sent_plus30 = True
        payment.save(update_fields=['alert_sent_plus30'])
        tenant = payment.tenant
        tenant.is_blocked = True
        tenant.save(update_fields=['is_blocked'])
        from apps.notifications.utils import notify
        notify(
            user=tenant,
            notification_type='system',
            title="Compte bloqué",
            body="Votre accès est restreint en raison d'un loyer impayé. Réglez votre situation pour retrouver l'accès.",
        )
        logger.warning(f"[CELERY] 🚫 Client bloqué — {tenant.get_full_name()}")

    logger.info("[CELERY] check_rent_payments terminé ✅")


@shared_task
def check_lease_renewals():
    """
    Vérifie chaque jour les baux qui approchent de leur fin.
    Envoie la notification au locataire à 83% de la durée.
    """
    from apps.contracts.models import LeaseContract
    from apps.notifications.utils import notify

    today = timezone.now().date()
    active_leases = LeaseContract.objects.filter(
        status='active',
        renewal_notified=False
    )

    for lease in active_leases:
        renewal_date = lease.get_renewal_notification_date()
        if today >= renewal_date:
            # Notifier le locataire
            notify(
                user=lease.tenant,
                notification_type='lease_renewal',
                title="Votre bail arrive bientôt à terme",
                body=f"Votre bail pour {lease.rental_property.title} expire le {lease.end_date}. Souhaitez-vous renouveler ?",
                data={'lease_id': str(lease.id)}
            )
            # Notifier l'agent
            if lease.agent:
                notify(
                    user=lease.agent,
                    notification_type='lease_renewal',
                    title="Bail bientôt expiré",
                    body=f"Le bail de {lease.tenant.get_full_name()} pour {lease.rental_property.title} expire le {lease.end_date}",
                )

            lease.renewal_notified    = True
            lease.renewal_notified_at = timezone.now()
            lease.save(update_fields=['renewal_notified', 'renewal_notified_at'])
            logger.info(f"[CELERY] Notification renouvellement → {lease.tenant.get_full_name()}")

    logger.info("[CELERY] check_lease_renewals terminé ✅")


@shared_task
def block_unpaid_clients():
    """Bloquer les clients avec loyer impayé depuis 30+ jours"""
    from apps.leases.models import RentPayment
    today = timezone.now().date()
    overdue = RentPayment.objects.filter(
        status='late',
        due_date__lte=today - timedelta(days=30)
    ).select_related('tenant')

    for payment in overdue:
        if not payment.tenant.is_blocked:
            payment.tenant.is_blocked = True
            payment.tenant.save(update_fields=['is_blocked'])
            logger.info(f"[CELERY] Client bloqué: {payment.tenant.get_full_name()}")


@shared_task
def generate_monthly_reports():
    """Génère les reçus PDF mensuels pour tous les locataires"""
    from apps.leases.models import RentPayment
    from apps.notifications.utils import notify

    last_month = timezone.now().replace(day=1) - timedelta(days=1)
    payments = RentPayment.objects.filter(
        status='paid',
        period_month=last_month.month,
        period_year=last_month.year
    ).select_related('tenant', 'lease')

    for payment in payments:
        notify(
            user=payment.tenant,
            notification_type='payment_success',
            title="Reçu mensuel disponible",
            body=f"Votre reçu de loyer pour {last_month.strftime('%B %Y')} est disponible.",
        )

    logger.info(f"[CELERY] {payments.count()} reçus mensuels générés ✅")
