import pytest
from rest_framework import status
from apps.referrals.models import Referral

pytestmark = pytest.mark.django_db


class TestReferrals:

    def test_get_my_referrals(self, auth_client, client_user):
        response = auth_client.get('/api/v1/referrals/mine/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'referral_code' in data
        assert data['referral_code'] is not None

    def test_referral_code_unique(self, create_user):
        user1 = create_user(email='ref1@test.com', phone='+237670000100', role='client')
        user2 = create_user(email='ref2@test.com', phone='+237670000101', role='client')
        assert user1.referral_code != user2.referral_code

    def test_unauthenticated_cannot_see_referrals(self, api_client):
        response = api_client.get('/api/v1/referrals/mine/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
