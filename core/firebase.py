import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

_firebase_app = None


def get_firebase_app():
    """Initialise Firebase une seule fois"""
    global _firebase_app
    if _firebase_app is None:
        try:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase initialisé ✅")
        except Exception as e:
            logger.error(f"Erreur Firebase: {e}")
    return _firebase_app


def send_push_notification(device_token, title, body, data=None):
    """
    Envoie une notification push à un appareil
    device_token: token FCM de l'appareil
    title: titre de la notification
    body: contenu de la notification
    data: données supplémentaires (dict)
    """
    try:
        get_firebase_app()
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=device_token,
        )
        response = messaging.send(message)
        logger.info(f"Notification envoyée: {response}")
        return {'success': True, 'message_id': response}
    except Exception as e:
        logger.error(f"Erreur notification push: {e}")
        return {'success': False, 'error': str(e)}


def send_push_to_multiple(device_tokens, title, body, data=None):
    """
    Envoie une notification push à plusieurs appareils
    """
    if not device_tokens:
        return {'success': False, 'error': 'Aucun token'}

    try:
        get_firebase_app()
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=device_tokens,
        )
        response = messaging.send_each_for_multicast(message)
        logger.info(f"Notifications envoyées: {response.success_count} succès, {response.failure_count} échecs")
        return {
            'success': True,
            'success_count': response.success_count,
            'failure_count': response.failure_count,
        }
    except Exception as e:
        logger.error(f"Erreur notifications multiples: {e}")
        return {'success': False, 'error': str(e)}


def send_notification_by_user(user, title, body, data=None):
    """
    Envoie une notification à tous les appareils d'un utilisateur
    """
    from apps.users.models import UserDevice
    tokens = list(
        UserDevice.objects.filter(
            user=user,
            is_active=True
        ).values_list('device_token', flat=True)
    )
    if not tokens:
        return {'success': False, 'error': 'Aucun appareil enregistré'}

    return send_push_to_multiple(tokens, title, body, data)
