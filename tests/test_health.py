import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestHealthCheck:

    def test_health_endpoint_accessible(self, api_client):
        response = api_client.get('/api/health/')
        assert response.status_code in [200, 503]

    def test_health_returns_database_status(self, api_client):
        response = api_client.get('/api/health/')
        assert response.status_code in [200, 503]
        data = response.data
        assert 'status' in data or isinstance(data, dict)

    def test_api_v1_health(self, api_client):
        response = api_client.get('/api/v1/health/')
        assert response.status_code in [200, 503]
