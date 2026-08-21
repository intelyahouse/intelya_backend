import pytest
import uuid
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch
from rest_framework import status
from apps.payments.models import Transaction, Escrow

pytestmark = pytest.mark.django_db

MOCK_OK = {'success': True, 'reference': 'KPAY-OK', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
MOCK_FAIL = {'success': False, 'error': 'Fonds insuffisants'}


class TestInitierPaiement:

    def test_mtn_succes(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            r = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '5000', 'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert r.status_code == status.HTTP_201_CREATED
        assert 'reference' in r.data['data']

    def test_orange_succes(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            r = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '10000', 'payment_method': 'orange',
                'phone_number': '+237690000001',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert r.status_code == status.HTTP_201_CREATED

    def test_montant_trop_bas(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            r = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '50', 'payment_method': 'mtn',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_champs_manquants(self, auth_client):
        r = auth_client.post('/api/v1/payments/initiate/', {})
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_authentifie_bloque(self, api_client, property_obj):
        r = api_client.post('/api/v1/payments/initiate/', {
            'amount': '5000', 'payment_method': 'mtn',
            'related_type': 'visit', 'related_id': str(property_obj.id),
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_idempotence(self, auth_client, property_obj):
        unique_id = uuid.uuid4()
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            r1 = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '5000', 'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'visit', 'related_id': str(unique_id),
            })
            r2 = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '5000', 'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'visit', 'related_id': str(unique_id),
            })
        assert r1.status_code == status.HTTP_201_CREATED
        assert r2.status_code == status.HTTP_200_OK
        assert r2.data['message'] == 'Transaction déjà en cours'

    def test_escrow_cree(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            r = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '5000', 'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert r.status_code == status.HTTP_201_CREATED
        assert Escrow.objects.filter(transaction__id=r.data['data']['transaction_id']).exists()


class TestHistorique:

    def test_historique_vide(self, auth_client):
        r = auth_client.get('/api/v1/payments/history/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['count'] == 0

    def test_voir_mes_transactions(self, auth_client, client_user):
        Transaction.objects.create(
            reference='IH-H001', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        r = auth_client.get('/api/v1/payments/history/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['count'] >= 1

    def test_ne_voit_pas_autres_transactions(self, auth_client, agent_user):
        Transaction.objects.create(
            reference='IH-H002', payer=agent_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        r = auth_client.get('/api/v1/payments/history/')
        refs = [t['reference'] for t in r.data['results']]
        assert 'IH-H002' not in refs

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/payments/history/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_statut_paiement(self, auth_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-S001', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        r = auth_client.get(f'/api/v1/payments/status/{txn.reference}/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['data']['status'] == 'completed'

    def test_statut_inexistant_404(self, auth_client):
        r = auth_client.get('/api/v1/payments/status/IH-INCONNU/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_statut_autre_utilisateur_404(self, auth_client, agent_user):
        txn = Transaction.objects.create(
            reference='IH-S002', payer=agent_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='pending', payment_method='mtn',
        )
        r = auth_client.get(f'/api/v1/payments/status/{txn.reference}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND


class TestWebhookKPay:

    def test_webhook_succes(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-W001', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        r = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-T001', 'refid': 'IH-W001',
            'statusid': '01', 'statusdesc': 'Success',
        }, format='json')
        assert r.status_code == status.HTTP_200_OK
        assert r.data.get('reply') == 'OK'
        txn.refresh_from_db()
        assert txn.status == 'completed'

    def test_webhook_echec(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-W002', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        r = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-T002', 'refid': 'IH-W002',
            'statusid': '02', 'statusdesc': 'Failed',
        }, format='json')
        assert r.status_code == status.HTTP_200_OK
        txn.refresh_from_db()
        assert txn.status == 'failed'

    def test_webhook_reference_inconnue(self, api_client):
        r = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-T999', 'refid': 'IH-INCONNU',
            'statusid': '01',
        }, format='json')
        assert r.status_code == status.HTTP_200_OK
        assert r.data.get('reply') == 'OK'

    def test_webhook_sans_refid(self, api_client):
        r = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-NOREF', 'statusid': '01',
        }, format='json')
        assert r.status_code == status.HTTP_200_OK

    def test_escrow_libere_apres_succes(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-W003', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        escrow = Escrow.objects.create(
            transaction=txn, amount=5000, held_for=client_user,
            release_after=timezone.now() + timedelta(hours=24),
        )
        api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-T003', 'refid': 'IH-W003',
            'statusid': '01', 'statusdesc': 'Success',
        }, format='json')
        escrow.refresh_from_db()
        assert escrow.status == 'released'

    def test_escrow_rembourse_apres_echec(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-W004', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        escrow = Escrow.objects.create(
            transaction=txn, amount=5000, held_for=client_user,
            release_after=timezone.now() + timedelta(hours=24),
        )
        api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-T004', 'refid': 'IH-W004',
            'statusid': '02', 'statusdesc': 'Failed',
        }, format='json')
        escrow.refresh_from_db()
        assert escrow.status == 'refunded'


class TestWebhookIdempotence:
    """Un fournisseur de paiement peut retransmettre le meme webhook
    'succes' plusieurs fois (retry sans reponse 200 a temps, etc.). Sans
    garde, chaque retransmission relancait _transfer_to_owner et versait
    le proprietaire une deuxieme fois -- l'idempotence documentee dans
    disbursement.py n'etait en realite appliquee qu'a la part agence."""

    def _rent_lease(self, owner_user, client_user, property_obj):
        import datetime
        from apps.contracts.models import LeaseContract
        from apps.owners.models import OwnerProfile
        OwnerProfile.objects.filter(user=owner_user).update(mtn_momo_number='+237670000003')
        return LeaseContract.objects.create(
            tenant=client_user, owner=owner_user, agent=None, agency=None,
            rental_property=property_obj, monthly_rent=30000, deposit_amount=60000,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=365),
            payment_day=5, status='active', signed_by_tenant=True, signed_by_owner=True,
        )

    def test_kpay_webhook_replay_does_not_double_pay_owner(self, api_client, owner_user, client_user, property_obj):
        lease = self._rent_lease(owner_user, client_user, property_obj)
        txn = Transaction.objects.create(
            reference='IH-W005', payer=client_user, receiver=owner_user,
            transaction_type='rent', amount=30500,
            platform_fee=0, net_amount=30000, agency_fee_amount=0,
            currency='FCFA', status='processing', payment_method='mtn',
            related_lease_id=lease.id,
        )
        payload = {'tid': 'KPAY-T005', 'refid': 'IH-W005', 'statusid': '01', 'statusdesc': 'Success'}
        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value={'success': True, 'reference': 'X'}) as mocked_disburse:
            api_client.post('/api/v1/payments/webhook/kpay/', payload, format='json')
            api_client.post('/api/v1/payments/webhook/kpay/', payload, format='json')
        assert mocked_disburse.call_count == 1
        txn.refresh_from_db()
        assert txn.status == 'completed'

    def test_campay_webhook_replay_does_not_double_pay_owner(self, api_client, owner_user, client_user, property_obj):
        lease = self._rent_lease(owner_user, client_user, property_obj)
        txn = Transaction.objects.create(
            reference='IH-W006', external_reference='IH-W006',
            payer=client_user, receiver=owner_user,
            transaction_type='rent', amount=30500,
            platform_fee=0, net_amount=30000, agency_fee_amount=0,
            currency='FCFA', status='processing', payment_method='mtn',
            related_lease_id=lease.id,
        )
        payload = {'reference': 'IH-W006', 'status': 'SUCCESSFUL'}
        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value={'success': True, 'reference': 'X'}) as mocked_disburse:
            api_client.post('/api/v1/payments/webhook/campay/', payload, format='json')
            api_client.post('/api/v1/payments/webhook/campay/', payload, format='json')
        assert mocked_disburse.call_count == 1
        txn.refresh_from_db()
        assert txn.status == 'completed'
