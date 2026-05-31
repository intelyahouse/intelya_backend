"""
Service Push Notifications via Firebase Cloud Messaging
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class PushNotificationService:

    def __init__(self):
        self.initialized = False
        self._init_firebase()

    def _init_firebase(self):
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            if not firebase_admin._apps:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
            self.messaging  = messaging
            self.initialized = True
            logger.info("[FIREBASE] Initialisé ✅")
        except Exception as e:
            logger.warning(f"[FIREBASE] Non disponible: {e}")

    def send_to_user(self, user, title, body, data=None):
        """Envoyer une notification push à un utilisateur"""
        tokens = list(
            user.devices.filter(is_active=True).values_list('device_token', flat=True)
        )
        if not tokens:
            logger.info(f"[PUSH] Aucun device pour {user.get_full_name()}")
            return False

        if not self.initialized:
            logger.info(f"[PUSH SIMULATION] → {user.get_full_name()}: {title}")
            return True

        try:
            message = self.messaging.MulticastMessage(
                tokens=tokens,
                notification=self.messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in (data or {}).items()},
                android=self.messaging.AndroidConfig(priority='high'),
                apns=self.messaging.APNSConfig(
                    payload=self.messaging.APNSPayload(
                        aps=self.messaging.Aps(sound='default')
                    )
                )
            )
            response = self.messaging.send_multicast(message)
            logger.info(f"[PUSH] Envoyé à {user.get_full_name()}: {response.success_count} succès")
            return True
        except Exception as e:
            logger.error(f"[PUSH] Erreur: {e}")
            return False


push_service = PushNotificationService()
