"""
Service Campay — MTN Mobile Money + Orange Money Cameroun
Remplace les clés dans .env quand tu as les vraies APIs du professeur
Documentation: https://campay.net/fr/docs/
"""
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CampayService:

    BASE_URL = "https://demo.campay.net/api"  # Sandbox
    # BASE_URL = "https://campay.net/api"     # Production

    def __init__(self):
        self.api_key  = settings.ORANGE_MONEY_API_KEY
        self.api_url  = settings.ORANGE_MONEY_API_URL or self.BASE_URL
        self.username = getattr(settings, 'CAMPAY_USERNAME', '')
        self.password = getattr(settings, 'CAMPAY_PASSWORD', '')
        self.token    = None

    def get_token(self):
        """Obtenir le token d'authentification Campay"""
        try:
            resp = requests.post(
                f"{self.BASE_URL}/token/",
                json={'username': self.username, 'password': self.password},
                timeout=30
            )
            if resp.status_code == 200:
                self.token = resp.json().get('token')
                return self.token
        except Exception as e:
            logger.error(f"[CAMPAY] Erreur token: {e}")
        return None

    def collect(self, phone, amount, reference, description="Paiement INTELYA HAVEN"):
        """
        Initier un paiement Mobile Money (MTN ou Orange)
        phone: numéro au format +237XXXXXXXXX
        amount: montant en FCFA
        reference: référence unique de la transaction
        """
        token = self.get_token()
        if not token:
            return {'success': False, 'error': 'Authentification échouée'}

        try:
            resp = requests.post(
                f"{self.BASE_URL}/collect/",
                json={
                    'amount': str(amount),
                    'currency': 'XAF',
                    'from': phone,
                    'description': description,
                    'external_reference': reference,
                    'redirect_url': ''
                },
                headers={'Authorization': f'Token {token}'},
                timeout=30
            )
            data = resp.json()
            if resp.status_code in [200, 201]:
                return {
                    'success': True,
                    'reference': data.get('reference'),
                    'status': data.get('status'),
                    'ussd_code': data.get('ussd_code', ''),
                }
            return {'success': False, 'error': data.get('message', 'Erreur inconnue')}
        except Exception as e:
            logger.error(f"[CAMPAY] Erreur collect: {e}")
            return {'success': False, 'error': str(e)}

    def check_status(self, reference):
        """Vérifier le statut d'un paiement"""
        token = self.get_token()
        if not token:
            return {'success': False, 'error': 'Authentification échouée'}

        try:
            resp = requests.get(
                f"{self.BASE_URL}/transaction/{reference}/",
                headers={'Authorization': f'Token {token}'},
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'success': True,
                    'status': data.get('status'),
                    'amount': data.get('amount'),
                    'operator': data.get('operator'),
                }
            return {'success': False, 'error': 'Transaction introuvable'}
        except Exception as e:
            logger.error(f"[CAMPAY] Erreur check: {e}")
            return {'success': False, 'error': str(e)}

    def disburse(self, phone, amount, reference, description="Virement INTELYA HAVEN"):
        """
        Virer de l'argent vers un compte Mobile Money (propriétaire, agent)
        """
        token = self.get_token()
        if not token:
            return {'success': False, 'error': 'Authentification échouée'}

        try:
            resp = requests.post(
                f"{self.BASE_URL}/disburse/",
                json={
                    'amount': str(amount),
                    'currency': 'XAF',
                    'to': phone,
                    'description': description,
                    'external_reference': reference,
                },
                headers={'Authorization': f'Token {token}'},
                timeout=30
            )
            data = resp.json()
            if resp.status_code in [200, 201]:
                return {'success': True, 'reference': data.get('reference')}
            return {'success': False, 'error': data.get('message', 'Erreur')}
        except Exception as e:
            logger.error(f"[CAMPAY] Erreur disburse: {e}")
            return {'success': False, 'error': str(e)}


campay_service = CampayService()
