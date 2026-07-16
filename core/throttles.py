from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class AuthThrottle(UserRateThrottle):
    """Connexion et inscription — 10/minute"""
    scope = 'auth'


class PaymentThrottle(UserRateThrottle):
    """Paiements — 20/heure"""
    scope = 'payments'


class UploadThrottle(UserRateThrottle):
    """Uploads fichiers — 30/heure"""
    scope = 'uploads'


class SearchThrottle(UserRateThrottle):
    """Recherche biens — 200/heure"""
    scope = 'search'
