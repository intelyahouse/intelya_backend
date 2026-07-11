from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.utils import generate_referral_code
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def verify_google_token(token):
    """
    Vérifie le token Google et retourne les infos de l'utilisateur
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        return {
            'success': True,
            'email': idinfo.get('email'),
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'google_id': idinfo.get('sub'),
            'profile_photo_url': idinfo.get('picture', ''),
        }
    except Exception as e:
        logger.error(f"Erreur vérification token Google: {e}")
        return {'success': False, 'error': str(e)}


def get_or_create_google_user(google_data):
    """
    Crée ou récupère un utilisateur depuis les données Google
    Retourne (user, created, needs_phone)
    """
    email = google_data.get('email')
    if not email:
        return None, False, False

    try:
        user = User.objects.get(email=email)
        needs_phone = not user.is_phone_verified
        return user, False, needs_phone
    except User.DoesNotExist:
        pass

    referral_code = generate_referral_code()
    while User.objects.filter(referral_code=referral_code).exists():
        referral_code = generate_referral_code()

    user = User.objects.create(
        email=email,
        first_name=google_data.get('first_name', ''),
        last_name=google_data.get('last_name', ''),
        role='client',
        referral_code=referral_code,
        is_active=True,
        is_phone_verified=False,
        date_joined=timezone.now(),
    )
    user.set_unusable_password()
    user.save()

    return user, True, True
