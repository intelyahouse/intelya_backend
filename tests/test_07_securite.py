import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestAuthSecurity:

    PROTECTED_ENDPOINTS = [
        ('/api/v1/users/me/', 'get'),
        ('/api/v1/admin-panel/stats/', 'get'),
        ('/api/v1/visits/', 'get'),
        ('/api/v1/leases/payments/', 'get'),
        ('/api/v1/messaging/conversations/', 'get'),
        ('/api/v1/notifications/', 'get'),
        ('/api/v1/referrals/mine/', 'get'),
        ('/api/v1/boost/mine/', 'get'),
    ]

    def test_all_protected_endpoints_require_auth(self, api_client):
        for url, method in self.PROTECTED_ENDPOINTS:
            response = getattr(api_client, method)(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Endpoint {url} devrait exiger une authentification"

    ADMIN_ONLY_ENDPOINTS = [
        '/api/v1/admin-panel/stats/',
        '/api/v1/admin-panel/users/',
        '/api/v1/admin-panel/transactions/',
        '/api/v1/admin-panel/revenue/',
    ]

    def test_admin_endpoints_blocked_for_clients(self, auth_client):
        for url in self.ADMIN_ONLY_ENDPOINTS:
            response = auth_client.get(url)
            assert response.status_code == status.HTTP_403_FORBIDDEN, \
                f"Endpoint {url} doit être réservé aux admins"

    def test_admin_endpoints_blocked_for_agents(self, auth_agent):
        for url in self.ADMIN_ONLY_ENDPOINTS:
            response = auth_agent.get(url)
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_endpoints_accessible_for_admin(self, auth_admin):
        for url in self.ADMIN_ONLY_ENDPOINTS:
            response = auth_admin.get(url)
            assert response.status_code == status.HTTP_200_OK, \
                f"Admin devrait accéder à {url}"


class TestIDORProtection:

    def test_cannot_access_other_user_visits(self, api_client, client_user, create_user,
                                              agent_user, property_obj):
        from apps.agents.models import ClientAgentRelation
        from apps.visits.models import VisitRequest
        ClientAgentRelation.objects.get_or_create(client=client_user, agent=agent_user)
        visit = VisitRequest.objects.create(
            client=client_user, agent=agent_user,
            visit_property=property_obj, status='scheduled',
        )

        other_user = create_user(
            email='other_idor@test.com', phone='+237670000080', role='client'
        )
        api_client.force_authenticate(user=other_user)

        response = api_client.post(f'/api/v1/visits/{visit.id}/cancel/', {
            'reason': 'Tentative IDOR'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_see_other_profile_data(self, auth_client, admin_user):
        response = auth_client.get(f'/api/v1/admin-panel/users/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestInputValidation:

    def test_sql_injection_in_login(self, api_client):
        for payload in ["' OR '1'='1", "1'; DROP TABLE users; --", "admin'--"]:
            response = api_client.post('/api/v1/auth/login/', {
                'email': payload,
                'password': 'anything'
            })
            assert response.status_code in [400, 401], \
                f"SQL injection '{payload}' devrait être bloquée"

    def test_xss_in_registration(self, api_client):
        xss_payloads = [
            '<script>alert("xss")</script>',
            'javascript:alert(1)',
            '<img src=x onerror=alert(1)>',
        ]
        for payload in xss_payloads:
            response = api_client.post('/api/v1/auth/register/', {
                'first_name': payload,
                'last_name': 'Test',
                'email': f'xss_{hash(payload)}@test.com',
                'phone': '+237670000090',
                'password': 'TestPass123!',
                'confirm_password': 'TestPass123!',
            })
            if response.status_code == 201:
                assert '<script>' not in str(response.data)
                assert 'javascript:' not in str(response.data)

    def test_invalid_uuid_returns_404(self, api_client):
        response = api_client.get('/api/v1/properties/not-a-valid-uuid/')
        assert response.status_code in [400, 404]

    def test_very_long_input_blocked(self, api_client):
        response = api_client.post('/api/v1/auth/login/', {
            'email': 'a' * 10000 + '@test.com',
            'password': 'a' * 10000,
        })
        assert response.status_code in [400, 401]


class TestPropertySecurity:

    def test_property_full_address_never_in_list(self, api_client, property_obj):
        response = api_client.get('/api/v1/properties/')
        response_text = str(response.data)
        assert 'Rue Test N°1' not in response_text, \
            "L'adresse complète ne doit JAMAIS apparaître dans la liste"

    def test_property_full_address_not_in_detail_for_client(self, auth_client, property_obj):
        response = auth_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert 'full_address' not in response.data.get('data', {})

    def test_only_agent_can_create_property(self, auth_client, auth_owner, owner_user):
        data = {'owner_id': str(owner_user.id), 'title': 'Test', 'price': 100000}
        assert auth_client.post('/api/v1/properties/create/', data).status_code == status.HTTP_403_FORBIDDEN
        assert auth_owner.post('/api/v1/properties/create/', data).status_code == status.HTTP_403_FORBIDDEN


class TestAdminSecurity:

    def test_admin_can_see_full_addresses(self, auth_admin, property_obj):
        response = auth_admin.get('/api/v1/admin-panel/properties/')
        assert response.status_code == status.HTTP_200_OK

    def test_admin_validate_user(self, auth_admin, create_user):
        pending_user = create_user(
            email='pending@test.com', phone='+237680000001',
            role='agent',
        )
        response = auth_admin.post(
            f'/api/v1/admin-panel/users/{pending_user.id}/validate/',
            {'action': 'approve', 'note': 'Documents vérifiés'}
        )
        assert response.status_code == status.HTTP_200_OK
        pending_user.refresh_from_db()
        assert pending_user.is_validated is True

    def test_admin_reject_user(self, auth_admin, create_user):
        pending_user = create_user(
            email='toreject@test.com', phone='+237680000002',
            role='agent',
        )
        response = auth_admin.post(
            f'/api/v1/admin-panel/users/{pending_user.id}/validate/',
            {'action': 'reject', 'note': 'Documents invalides'}
        )
        assert response.status_code == status.HTTP_200_OK
        pending_user.refresh_from_db()
        assert pending_user.is_validated is False

    def test_admin_block_user(self, auth_admin, client_user):
        response = auth_admin.post(
            f'/api/v1/admin-panel/users/{client_user.id}/block/',
            {'action': 'block'}
        )
        assert response.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.is_blocked is True

    def test_admin_unblock_user(self, auth_admin, client_user):
        client_user.is_blocked = True
        client_user.save()
        response = auth_admin.post(
            f'/api/v1/admin-panel/users/{client_user.id}/block/',
            {'action': 'unblock'}
        )
        assert response.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.is_blocked is False
