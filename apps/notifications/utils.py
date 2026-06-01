"""
Utilitaires pour créer et envoyer les notifications
"""
from .models import Notification
from .services.push import push_service
from django.utils import timezone


def notify(user, notification_type, title, body, data=None, send_push=True):
    """Créer une notification en base + envoyer push"""
    notification = Notification.objects.create(
        recipient=user,
        notification_type=notification_type,
        title=title,
        body=body,
        data=data or {}
    )
    if send_push:
        push_service.send_to_user(user, title, body, data)
    return notification


def notify_visit_request(agent, client_name, property_title):
    notify(
        user=agent,
        notification_type='visit_request',
        title="Nouvelle demande de visite",
        body=f"{client_name} veut visiter : {property_title}",
    )


def notify_visit_scheduled(client, property_title, date, time):
    notify(
        user=client,
        notification_type='visit_scheduled',
        title="Visite planifiée ✅",
        body=f"Votre visite de {property_title} est prévue le {date} à {time}",
    )


def notify_rent_reminder(tenant, amount, due_date):
    notify(
        user=tenant,
        notification_type='rent_reminder',
        title="Rappel loyer",
        body=f"Votre loyer de {amount} FCFA est dû le {due_date}",
    )


def notify_rent_late(agent, tenant_name, amount):
    notify(
        user=agent,
        notification_type='rent_late',
        title="Loyer en retard",
        body=f"{tenant_name} n'a pas payé son loyer de {amount} FCFA",
    )


def notify_account_validated(user):
    notify(
        user=user,
        notification_type='account_validated',
        title="Compte validé ✅",
        body="Votre compte INTELYA HAVEN a été validé. Vous pouvez maintenant accéder à toutes les fonctionnalités.",
    )


def notify_payment_success(user, amount):
    notify(
        user=user,
        notification_type='payment_success',
        title="Paiement réussi ✅",
        body=f"Votre paiement de {amount} FCFA a été traité avec succès.",
    )


def notify_boost_expired(agent):
    notify(
        user=agent,
        notification_type='boost_expired',
        title="Boost expiré",
        body="Votre boost de visibilité a expiré. Renouvelez pour rester en tête des résultats.",
    )


def notify_complaint_new(assigned_to, tenant_name, category):
    notify(
        user=assigned_to,
        notification_type='complaint_new',
        title="Nouvelle plainte",
        body=f"{tenant_name} a soumis une plainte : {category}",
    )


def notify_bulk(users, notification_type, title, body, data=None):
    """
    Envoie une notification a plusieurs utilisateurs en UNE seule requete SQL.
    Utiliser pour les notifications de masse.
    """
    from .models import Notification
    notifications = [
        Notification(
            recipient=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {}
        )
        for user in users
    ]
    Notification.objects.bulk_create(notifications, batch_size=1000)

    # Push en arriere-plan via Celery
    from .tasks import send_bulk_push_task
    user_ids = [str(u.id) for u in users]
    send_bulk_push_task.delay(user_ids, title, body, data or {})
