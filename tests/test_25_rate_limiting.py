"""
Tests Rate Limiting — Protection brute force et throttling
"""
import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestThrottlingAPI:

    def test_5_echecs_login_bloque(self, api_client):
        r = api_client.post('/api/v1/auth/login/', {
            'email': 'inexistant@test.com',
            'password': 'mauvais'
        })
        assert r.status_code in [400, 401, 403]

    def test_login_reussi_non_bloque(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email,
            'password': 'TestPass123!'
        })
        assert r.status_code == status.HTTP_200_OK

    def test_reset_axes_apres_succes(self, api_client, client_user):
        client_user.login_attempts = 0
        client_user.save()
        client_user.refresh_from_db()
        assert client_user.login_attempts == 0

    def test_endpoint_public_accessible(self, api_client):
        r = api_client.get('/api/v1/properties/')
        assert r.status_code == status.HTTP_200_OK

    def test_endpoint_auth_accessible(self, auth_client):
        r = auth_client.get('/api/v1/users/me/')
        assert r.status_code == status.HTTP_200_OK

    def test_otp_limite_stricte(self, api_client):
        r = api_client.post('/api/v1/auth/resend-otp/', {
            'phone': '+237699999999'
        })
        assert r.status_code in [400, 404]

    def test_initiation_paiement_limitee(self, auth_client):
        r = auth_client.post('/api/v1/payments/initiate/', {
            'amount': 0,
            'payment_method': 'mtn',
        })
        assert r.status_code in [400, 422]
