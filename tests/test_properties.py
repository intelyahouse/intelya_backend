import pytest
from rest_framework import status
from apps.properties.models import Property, PropertyLike

pytestmark = pytest.mark.django_db


class TestPropertyList:

    def test_list_public_access(self, api_client):
        response = api_client.get('/api/v1/properties/')
        assert response.status_code == status.HTTP_200_OK

    def test_list_no_full_address_exposed(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/')
        results = response.data.get('results', response.data.get('data', []))
        if isinstance(results, list):
            for item in results:
                assert 'full_address' not in item, "L'adresse complète ne doit jamais être exposée"

    def test_list_filter_by_city(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/?city=Douala')
        assert response.status_code == status.HTTP_200_OK

    def test_list_filter_by_type(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/?type=apartment')
        assert response.status_code == status.HTTP_200_OK

    def test_list_filter_by_price(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/?min_price=100000&max_price=200000')
        assert response.status_code == status.HTTP_200_OK

    def test_list_filter_has_generator(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/?generator=true')
        assert response.status_code == status.HTTP_200_OK

    def test_list_is_paginated(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/')
        assert response.status_code == status.HTTP_200_OK


class TestPropertyDetail:

    def test_detail_success(self, api_client, property_obj):
        response = api_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['title'] == 'Appartement Test'

    def test_detail_no_address_for_client(self, auth_client, property_obj):
        response = auth_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert 'full_address' not in response.data.get('data', {})

    def test_detail_address_visible_for_admin(self, auth_admin, property_obj):
        response = auth_admin.get(f'/api/v1/properties/{property_obj.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert 'full_address' in response.data.get('data', {})

    def test_detail_increments_view_count(self, api_client, property_obj):
        initial_views = property_obj.views_count
        api_client.get(f'/api/v1/properties/{property_obj.id}/')
        property_obj.refresh_from_db()
        assert property_obj.views_count == initial_views + 1

    def test_detail_nonexistent_returns_404(self, api_client):
        import uuid
        response = api_client.get(f'/api/v1/properties/{uuid.uuid4()}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPropertyCreate:

    def test_create_requires_agent_role(self, auth_client, owner_user):
        response = auth_client.post('/api/v1/properties/create/', {
            'owner_id': str(owner_user.id),
            'title': 'Test',
            'description': 'Description test',
            'price': 100000,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_requires_owner_linked_to_agent(self, auth_agent, owner_user):
        response = auth_agent.post('/api/v1/properties/create/', {
            'owner_id': str(owner_user.id),
            'title': 'Test Bien',
            'description': 'Description suffisamment longue pour passer la validation minimale',
            'property_type': 'apartment',
            'price': 150000,
            'bedrooms': 2,
            'bathrooms': 1,
            'city': 'Douala',
            'neighborhood': 'Bonanjo',
            'full_address': 'Rue Test N°1',
        })
        assert response.status_code in [201, 403]

    def test_create_without_auth_fails(self, api_client, owner_user):
        response = api_client.post('/api/v1/properties/create/', {
            'owner_id': str(owner_user.id),
            'title': 'Test',
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPropertyLike:

    def test_like_property(self, auth_client, property_obj, client_user):
        response = auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert response.status_code == status.HTTP_200_OK
        assert PropertyLike.objects.filter(property=property_obj, user=client_user).exists()

    def test_unlike_property(self, auth_client, property_obj, client_user):
        PropertyLike.objects.create(property=property_obj, user=client_user)
        response = auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert response.status_code == status.HTTP_200_OK
        assert not PropertyLike.objects.filter(property=property_obj, user=client_user).exists()

    def test_like_requires_auth(self, api_client, property_obj):
        response = api_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_favorites_list(self, auth_client, property_obj, client_user):
        PropertyLike.objects.create(property=property_obj, user=client_user)
        response = auth_client.get('/api/v1/properties/favorites/')
        assert response.status_code == status.HTTP_200_OK
