"""
Service K-Pay — MTN Mobile Money + Orange Money + Carte bancaire
API Endpoint : https://pay.esicia.com/
Documentation : https://www.kpay.africa/docs/
Mettre les vraies clés dans .env quand le prof les donne
"""
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class KPayService:

    BASE_URL = "https://pay.esicia.com/"

    def __init__(self):
        self.api_key    = getattr(settings, 'KPAY_API_KEY', '')
        self.retailer_id = getattr(settings, 'KPAY_RETAILER_ID', '')
        self.returl     = getattr(settings, 'KPAY_WEBHOOK_URL', '')
        self.redirecturl = getattr(settings, 'KPAY_REDIRECT_URL', '')

    def _pmethod(self, method: str) -> str:
        """Convertir notre méthode interne vers le format K-Pay"""
        mapping = {
            'mtn':    'momo',
            'orange': 'momo',
            'card':   'cc',
            'visa':   'cc',
            'mastercard': 'cc',
        }
        return mapping.get(method.lower(), 'momo')

    def collect(self, phone: str, amount: int, reference: str,
                description: str = "Paiement INTELYA HAVEN",
                method: str = 'mtn', user_name: str = '',
                user_email: str = '', customer_number: str = ''):
        """
        Initier un paiement Mobile Money ou carte bancaire
        phone      : numéro avec indicatif pays sans + (ex: 237670000001)
        amount     : montant en FCFA
        reference  : référence unique de la transaction
        method     : mtn | orange | card | visa | mastercard
        """
        # Nettoyer le numéro de téléphone (enlever le +)
        phone_clean = phone.replace('+', '').replace(' ', '')

        payload = {
            "action":      "pay",
            "msisdn":      phone_clean,
            "details":     description,
            "refid":       reference,
            "amount":      amount,
            "currency":    "XAF",
            "email":       user_email or f"{reference}@intelya.cm",
            "cname":       user_name or "Client INTELYA",
            "cnumber":     customer_number or phone_clean,
            "pmethod":     self._pmethod(method),
            "retailerid":  self.retailer_id,
            "returl":      self.returl,
            "redirecturl": self.redirecturl,
        }

        headers = {
            "secret_key":   self.api_key,
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                self.BASE_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            data = resp.json()
            logger.info(f"[KPAY] collect response: {data}")

            if data.get('success') == 1 or data.get('retcode') == 0:
                return {
                    'success':    True,
                    'reference':  data.get('tid', reference),
                    'status':     'pending',
                    'ussd_code':  '',
                    'checkout_url': data.get('url', ''),
                    'authkey':    data.get('authkey', ''),
                }

            return {
                'success': False,
                'error':   data.get('reply', 'Erreur inconnue'),
                'retcode': data.get('retcode'),
            }

        except Exception as e:
            logger.error(f"[KPAY] Erreur collect: {e}")
            return {'success': False, 'error': str(e)}

    def check_status(self, reference: str):
        """
        Vérifier le statut d'un paiement via refid
        """
        payload = {
            "action": "checkstatus",
            "refid":  reference,
        }

        headers = {
            "secret_key":   self.api_key,
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                self.BASE_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            data = resp.json()
            logger.info(f"[KPAY] checkstatus response: {data}")

            status_id = data.get('statusid', '02')
            success = status_id == '01'

            return {
                'success':  success,
                'status':   'completed' if success else 'failed',
                'tid':      data.get('tid'),
                'refid':    data.get('refid'),
                'operator_ref': data.get('momtransactionid'),
                'message':  data.get('statusdesc', ''),
            }

        except Exception as e:
            logger.error(f"[KPAY] Erreur checkstatus: {e}")
            return {'success': False, 'error': str(e)}

    def disburse(self, phone: str, amount: int, reference: str,
                 description: str = "Virement INTELYA HAVEN"):
        """
        Virer de l'argent vers un Mobile Money
        K-Pay utilise la même URL avec action=pay en sens inverse
        À confirmer avec les accès production du professeur
        """
        logger.info(f"[KPAY] disburse vers {phone} montant {amount} ref {reference}")
        # Sera implémenté avec les vraies clés de production
        return {'success': True, 'reference': reference}


kpay_service = KPayService()
