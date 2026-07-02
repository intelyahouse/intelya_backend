"""
Service SMS — via API du professeur
"""
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SMSService:

    def __init__(self):
        self.api_key    = settings.SMS_API_KEY
        self.api_url    = settings.SMS_API_URL
        self.sender     = settings.SMS_SENDER_NAME

    def send(self, phone, message):
        """Envoyer un SMS"""
        if not self.api_key or not self.api_url:
            # Simulation en dev — affiche dans le terminal
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

    def send_otp(self, phone, code):
        return self.send(phone, f"INTELYA HAVEN - Votre code de vérification est : {code}. Valable 15 minutes.")

    def send_rent_reminder(self, phone, amount, due_date):
        return self.send(phone, f"INTELYA HAVEN - Rappel : Votre loyer de {amount} FCFA est dû le {due_date}.")

    def send_account_validated(self, phone, role):
        return self.send(phone, f"INTELYA HAVEN - Votre compte {role} a été validé. Bienvenue !")

    def send_payment_received(self, phone, amount):
        return self.send(phone, f"INTELYA HAVEN - Paiement de {amount} FCFA reçu avec succès.")


sms_service = SMSService()
