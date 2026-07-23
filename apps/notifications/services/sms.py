"""
Service SMS — via API du professeur
Peut aussi router vers l'email temporairement (settings.NOTIFICATION_CHANNEL = 'email')
"""
import requests
from django.conf import settings
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)


class SMSService:

    def __init__(self):
        self.api_key    = settings.SMS_API_KEY
        self.api_url    = settings.SMS_API_URL
        self.sender     = settings.SMS_SENDER_NAME

    def send(self, phone, message, email=None, subject="INTELYA HAVEN"):
        """Envoyer une notification — email si NOTIFICATION_CHANNEL='email' et email fourni, sinon SMS"""
        if getattr(settings, 'NOTIFICATION_CHANNEL', 'sms') == 'email' and email:
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
                logger.info(f"[EMAIL] Envoyé à {email}")
                return True
            except Exception as e:
                logger.error(f"[EMAIL] Exception: {e}")
                return False

        if not self.api_key or not self.api_url:
            print(f"\n📱 [SMS → {phone}]\n{message}\n")
            logger.info(f"[SMS SIMULATION] → {phone}: {message[:50]}...")
            return True

        try:
            resp = requests.post(
                self.api_url,
                json={
                    'to': phone,
                    'message': message,
                    'sender': self.sender,
                    'api_key': self.api_key
                },
                timeout=15
            )
            success = resp.status_code in [200, 201]
            if success:
                logger.info(f"[SMS] Envoyé à {phone}")
            else:
                logger.error(f"[SMS] Erreur {resp.status_code}: {resp.text}")
            return success
        except Exception as e:
            logger.error(f"[SMS] Exception: {e}")
            return False

    def send_otp(self, phone, code, email=None):
        return self.send(
            phone, f"INTELYA HAVEN - Votre code de vérification est : {code}. Valable 15 minutes.",
            email=email, subject="Votre code de vérification INTELYA HAVEN"
        )

    def send_rent_reminder(self, phone, amount, due_date, email=None):
        return self.send(
            phone, f"INTELYA HAVEN - Rappel : Votre loyer de {amount} FCFA est dû le {due_date}.",
            email=email, subject="Rappel de loyer — INTELYA HAVEN"
        )

    def send_account_validated(self, phone, role, email=None):
        return self.send(
            phone, f"INTELYA HAVEN - Votre compte {role} a été validé. Bienvenue !",
            email=email, subject="Compte validé — INTELYA HAVEN"
        )

    def send_payment_received(self, phone, amount, email=None):
        return self.send(
            phone, f"INTELYA HAVEN - Paiement de {amount} FCFA reçu avec succès.",
            email=email, subject="Paiement reçu — INTELYA HAVEN"
        )


sms_service = SMSService()
