import pytest
from unittest.mock import patch
from rest_framework import status
from apps.payments.models import Transaction, Escrow

pytestmark = pytest.mark.django_db

KPAY_SUCCESS = {
    'success': 1,
    'reply': 'PENDING',
    'tid': 'KPAY-TID-001',
    'refid': 'IH-TEST',
    'retcode': 0,
    'authkey': 'abc123',
    'url': 'https://pay.esicia.com/checkout/ABC',
}

KPAY_FAIL = {
    'success': 0,
    'reply': 'TARGET_AUTHORIZATION_ERROR',
    'retcode': 606,
}


class TestInitiatePayment:

    def test_initiate_mtn_payment_success(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value={'success': True, 'reference': 'KPAY-TID-001', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}):
            response = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '5000',
                'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'visit',
                'related_id': str(property_obj.id),
            })
        assert response.status_code == status.HTTP_201_CREATED
        assert 'reference' in response.data['data']

    def test_initiate_orange_payment_success(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value={'success': True, 'reference': 'KPAY-TID-002', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}):
            response = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '10000',
                'payment_method': 'orange',
                'phone_number': '+237690000001',
                'related_type': 'visit',
                'related_id': str(property_obj.id),
            })
        assert response.status_code == status.HTTP_201_CREATED

    def test_initiate_payment_unauthenticated_fails(self, api_client, property_obj):
        response = api_client.post('/api/v1/payments/initiate/', {
            'amount': '5000', 'payment_method': 'mtn',
            'related_type': 'visit', 'related_id': str(property_obj.id),
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_initiate_payment_amount_too_low(self, auth_client, property_obj):
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value={'success': True}):
            response = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '50', 'payment_method': 'mtn',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_initiate_payment_missing_fields(self, auth_client):
        response = auth_client.post('/api/v1/payments/initiate/', {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_idempotency_no_double_payment(self, auth_client, property_obj):
        import uuid
        unique_id = uuid.uuid4()
        mock_result = {'success': True, 'reference': 'KPAY-789', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock_result):
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

    def test_escrow_created_for_visit_payment(self, auth_client, property_obj):
        mock_result = {'success': True, 'reference': 'KPAY-ESC', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock_result):
            response = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '5000', 'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert response.status_code == status.HTTP_201_CREATED
        txn_id = response.data['data']['transaction_id']
        assert Escrow.objects.filter(transaction__id=txn_id).exists()


class TestMyTransactions:

    def test_get_my_transactions_empty(self, auth_client):
        response = auth_client.get('/api/v1/payments/history/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0

    def test_get_my_transactions_shows_mine(self, auth_client, client_user):
        Transaction.objects.create(
            reference='IH-TEST-001', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        response = auth_client.get('/api/v1/payments/history/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] >= 1

    def test_cannot_see_other_user_transactions(self, auth_client, agent_user):
        Transaction.objects.create(
            reference='IH-TEST-002', payer=agent_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        response = auth_client.get('/api/v1/payments/history/')
        assert response.status_code == status.HTTP_200_OK
        refs = [t['reference'] for t in response.data['results']]
        assert 'IH-TEST-002' not in refs

    def test_unauthenticated_cannot_see_transactions(self, api_client):
        response = api_client.get('/api/v1/payments/history/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCheckPaymentStatus:

    def test_check_status_completed(self, auth_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-STATUS-001', payer=client_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        response = auth_client.get(f'/api/v1/payments/status/{txn.reference}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['status'] == 'completed'

    def test_check_status_not_found(self, auth_client):
        response = auth_client.get('/api/v1/payments/status/IH-INEXISTANT-999/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_check_other_user_payment(self, auth_client, agent_user):
        txn = Transaction.objects.create(
            reference='IH-OTHER-001', payer=agent_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='pending', payment_method='mtn',
        )
        response = auth_client.get(f'/api/v1/payments/status/{txn.reference}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestKPayWebhook:

    def test_webhook_payment_success(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-HOOK-001', external_reference='IH-HOOK-001',
            payer=client_user, transaction_type='visit',
            amount=5000, platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        response = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-TID-001',
            'refid': 'IH-HOOK-001',
            'momtransactionid': '616730887',
            'payaccount': '237670000001',
            'statusid': '01',
            'statusdesc': 'Successfully processed transaction.',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data.get('reply') == 'OK'
        txn.refresh_from_db()
        assert txn.status == 'completed'

    def test_webhook_payment_failed(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-HOOK-002', external_reference='IH-HOOK-002',
            payer=client_user, transaction_type='visit',
            amount=5000, platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        response = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-TID-002',
            'refid': 'IH-HOOK-002',
            'statusid': '02',
            'statusdesc': 'Payment failed.',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        txn.refresh_from_db()
        assert txn.status == 'failed'

    def test_webhook_unknown_reference_ignored(self, api_client):
        response = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-UNKNOWN',
            'refid': 'IH-INCONNU-999',
            'statusid': '01',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data.get('reply') == 'OK'

    def test_webhook_missing_refid_ignored(self, api_client):
        response = api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-NO-REF',
            'statusid': '01',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
