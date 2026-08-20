"""
Service Email — via SMTP configure dans les settings Django (EMAIL_BACKEND).
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class EmailNotificationService:

    def send(self, to_email, subject, body):
        if not to_email:
            return False
        if not settings.EMAIL_HOST_USER:
            # Simulation en dev — affiche dans le terminal
            print(f"\n📧 [EMAIL → {to_email}] {subject}\n{body}\n")
            logger.info(f"[EMAIL SIMULATION] → {to_email}: {subject}")
            return True

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            logger.info(f"[EMAIL] Envoyé à {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"[EMAIL] Erreur vers {to_email}: {e}")
            return False

    def send_otp(self, to_email, code):
        return self.send(
            to_email, "INTELYA HAVEN — Votre code de vérification",
            f"Votre code de vérification est : {code}. Valable {settings.OTP_EXPIRY_MINUTES} minutes."
        )

    def send_account_validated(self, to_email, full_name, role):
        role_label = {'agent': 'agent immobilier', 'owner': 'propriétaire'}.get(role, role)
        return self.send(
            to_email, "INTELYA HAVEN — Votre compte a été validé ✅",
            f"Bonjour {full_name},\n\n"
            f"Votre compte {role_label} sur INTELYA HAVEN a été validé par notre équipe. "
            f"Vous pouvez dès maintenant accéder à toutes les fonctionnalités de votre espace.\n\n"
            f"Bienvenue sur INTELYA HAVEN !"
        )

    def send_notification(self, to_email, title, body):
        return self.send(to_email, f"INTELYA HAVEN — {title}", body)


email_service = EmailNotificationService()
