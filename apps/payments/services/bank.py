"""
Service Comptes Bancaires
Remplace avec l'API réelle du professeur
"""
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class BankPaymentService:

    def __init__(self):
        self.api_key = settings.BANK_API_KEY
        self.api_url = settings.BANK_API_URL

    def initiate_payment(self, account_number, amount, reference, description=""):
        """Initier un paiement par compte bancaire"""
        if not self.api_key or not self.api_url:
            # Mode simulation si pas encore de vraie API
            logger.info(f"[BANK SIMULATION] Paiement {amount} FCFA → {account_number}")
            return {
                'success': True,
                'reference': f'BANK-{reference}',
                'status': 'pending',
                'message': 'Paiement initié (simulation)'
            }

        try:
            resp = requests.post(
                f"{self.api_url}/payment/initiate",
                json={
                    'account': account_number,
                    'amount': amount,
                    'reference': reference,
                    'description': description,
                    'currency': 'XAF'
                },
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=30
            )
            if resp.status_code in [200, 201]:
                return {'success': True, **resp.json()}
            return {'success': False, 'error': 'Erreur API bancaire'}
        except Exception as e:
            logger.error(f"[BANK] Erreur: {e}")
            return {'success': False, 'error': str(e)}

    def transfer_to_owner(self, account_number, amount, reference):
        """Virer le loyer au propriétaire"""
        return self.initiate_payment(account_number, amount, reference, "Loyer INTELYA HAVEN")


bank_service = BankPaymentService()
