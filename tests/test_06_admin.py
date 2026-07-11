import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestAdminDashboard:

    def test_stats_admin(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_200_OK

    def test_stats_bloquees_client(self, auth_client):
        r = auth_client.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_stats_bloquees_agent(self, auth_agent):
        r = auth_agent.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_stats_bloquees_owner(self, auth_owner):
        r = auth_owner.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_revenus_admin(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/revenue/')
        assert r.status_code == status.HTTP_200_OK

    def test_config_plateforme(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/config/')
        assert r.status_code == status.HTTP_200_OK


class TestAdminUtilisateurs:

    def test_voir_tous_utilisateurs(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/users/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_utilisateurs_en_attente(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/users/pending/')
        assert r.status_code == status.HTTP_200_OK

    def test_valider_utilisateur(self, auth_admin, agent_user):
        agent_user.is_validated = False
        agent_user.validation_status = 'pending'
        agent_user.save()
        r = auth_admin.post(f'/api/v1/admin-panel/users/{agent_user.id}/validate/', {
            'action': 'approve',
        })
        assert r.status_code in [200, 201]

    def test_rejeter_utilisateur(self, auth_admin, agent_user):
        agent_user.is_validated = False
        agent_user.validation_status = 'pending'
        agent_user.save()
        r = auth_admin.post(f'/api/v1/admin-panel/users/{agent_user.id}/validate/', {
            'action': 'reject', 'note': 'Documents invalides',
        })
        assert r.status_code in [200, 201]

    def test_bloquer_utilisateur(self, auth_admin, client_user):
        r = auth_admin.post(f'/api/v1/admin-panel/users/{client_user.id}/block/', {
            'action': 'block', 'reason': 'Comportement suspect',
        })
        assert r.status_code in [200, 201]

    def test_debloquer_utilisateur(self, auth_admin, client_user):
        client_user.is_blocked = True
        client_user.save()
        r = auth_admin.post(f'/api/v1/admin-panel/users/{client_user.id}/block/', {
            'action': 'unblock',
        })
        assert r.status_code in [200, 201]


class TestAdminBiens:

    def test_voir_tous_biens(self, auth_admin, property_obj):
        r = auth_admin.get('/api/v1/admin-panel/properties/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_toutes_transactions(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/transactions/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_tous_baux(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_tous_boosts(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/boosts/')
        assert r.status_code == status.HTTP_200_OK
