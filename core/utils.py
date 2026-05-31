
# INTELYA HAVEN - Utilitaires


import uuid
import random
import string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import math


def generate_otp(length=6):
    """Génère un code OTP à 6 chiffres"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])


def generate_referral_code(length=8):
    """Génère un code de parrainage unique"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


def generate_transaction_reference():
    """Génère une référence de transaction unique"""
    return f"IH-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    """
    Calcule la distance en mètres entre deux coordonnées GPS
    Formule Haversine
    """
    R = 6371000  # Rayon de la Terre en mètres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def is_within_radius(lat1, lon1, lat2, lon2, radius_meters=None):
    """Vérifie si deux points sont dans le rayon défini"""
    if radius_meters is None:
        radius_meters = settings.VISIT_GPS_RADIUS_METERS
    distance = calculate_distance_meters(lat1, lon1, lat2, lon2)
    return distance <= radius_meters, distance


def calculate_lease_renewal_date(start_date, end_date):
    """
    Calcule la date à laquelle envoyer le rappel de renouvellement
    (83% de la durée écoulée)
    """
    total_duration = (end_date - start_date).days
    renewal_day = int(total_duration * settings.LEASE_RENEWAL_PERCENT / 100)
    return start_date + timedelta(days=renewal_day)


def calculate_platform_commission(amount):
    """Calcule la commission de la plateforme (2%)"""
    commission_percent = settings.PLATFORM_COMMISSION_PERCENT
    commission = amount * commission_percent / 100
    owner_amount = amount - commission
    return {
        'total': amount,
        'platform_commission': round(commission, 2),
        'owner_amount': round(owner_amount, 2),
        'commission_percent': commission_percent,
    }


def format_fcfa(amount):
    """Formate un montant en FCFA"""
    return f"{int(amount):,} FCFA".replace(',', ' ')


def success_response(data=None, message="Succès", status_code=200):
    """Format standard de réponse succès"""
    response = {
        'success': True,
        'message': message,
    }
    if data is not None:
        response['data'] = data
    return response


def error_response(message="Erreur", errors=None, status_code=400):
    """Format standard de réponse erreur"""
    response = {
        'success': False,
        'message': message,
    }
    if errors is not None:
        response['errors'] = errors
    return response
