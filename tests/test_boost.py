import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestBoost:

    def test_get_prices_authenticated(self, auth_client):
        response = auth_client.get('/api/v1/boost/prices/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'prices' in data
        assert 'bronze' in data['prices']
        assert 'silver' in data['prices']
        assert 'gold' in data['prices']

    def test_activate_boost_requires_agent(self, auth_client):
        response = auth_client.post('/api/v1/boost/activate/', {
            'level': 'bronze',
            'duration_days': 7,
            'target_city': 'Douala',
            'payment_method': 'mtn',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_agent_can_activate_boost(self, auth_agent):
        response = auth_agent.post('/api/v1/boost/activate/', {
            'level': 'bronze',
            'duration_days': 7,
            'target_city': 'Douala',
            'payment_method': 'mtn',
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_my_boosts(self, auth_agent):
        response = auth_agent.get('/api/v1/boost/mine/')
        assert response.status_code == status.HTTP_200_OK
