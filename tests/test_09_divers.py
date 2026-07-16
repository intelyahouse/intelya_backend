"""
Tests divers — Notifications, Referrals, Health, Performance
Les tests complets sont dans les fichiers dédiés (test_11 à test_21)
"""
import pytest
import time
from rest_framework import status
from apps.payments.models import Transaction

pytestmark = pytest.mark.django_db


class TestNotifications:

    def test_voir_notifications(self, auth_client):
        r = auth_client.get('/api/v1/notifications/')
        assert r.status_code == status.HTTP_200_OK

    def test_marquer_lues(self, auth_client):
        r = auth_client.post('/api/v1/notifications/mark-read/')
        assert r.status_code in [200, 201]

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/notifications/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestReferrals:

    def test_voir_filleuls(self, auth_client):
        r = auth_client.get('/api/v1/referrals/mine/')
        assert r.status_code == status.HTTP_200_OK

    def test_codes_uniques(self, client_user, create_user):
        autre = create_user(email='ref2@test.cm', phone='+237670000070', role='client')
        assert client_user.referral_code != autre.referral_code
        assert client_user.referral_code is not None

    def test_non_authentifie_bloque_referrals(self, api_client):
        r = api_client.get('/api/v1/referrals/mine/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestHealthEtPerformance:

    def test_health_check(self, api_client):
        r = api_client.get('/api/health/')
        assert r.status_code == status.HTTP_200_OK

    def test_swagger_accessible(self, api_client):
        r = api_client.get('/api/docs/')
        assert r.status_code == status.HTTP_200_OK

    def test_api_rapide(self, api_client):
        start = time.time()
        api_client.get('/api/v1/properties/')
        assert time.time() - start < 2.0

    def test_5_requetes_rapides(self, api_client):
        start = time.time()
        for _ in range(5):
            api_client.get('/api/v1/properties/')
        assert time.time() - start < 5.0

    def test_transactions_indexees(self, auth_client, client_user):
        for i in range(10):
            Transaction.objects.create(
                reference=f'IH-IDX-{i:03d}', payer=client_user,
                transaction_type='visit', amount=5000,
                platform_fee=100, net_amount=4900,
                currency='FCFA', status='completed', payment_method='mtn',
            )
        start = time.time()
        auth_client.get('/api/v1/payments/history/')
        assert time.time() - start < 2.0
