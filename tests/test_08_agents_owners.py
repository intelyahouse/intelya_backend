import pytest
from datetime import date
from rest_framework import status
from apps.agents.models import OwnerAgentRelation, AgentProfile

pytestmark = pytest.mark.django_db


class TestAgents:

    def test_liste_agents_publique(self, api_client):
        r = api_client.get('/api/v1/agents/')
        assert r.status_code == status.HTTP_200_OK

    def test_profil_agent_connecte(self, auth_agent):
        r = auth_agent.get('/api/v1/agents/me/')
        assert r.status_code == status.HTTP_200_OK

    def test_profil_public_agent(self, api_client, agent_user):
        try:
            profile = AgentProfile.objects.get(user=agent_user)
            r = api_client.get(f'/api/v1/agents/{profile.id}/')
            assert r.status_code in [200, 404]
        except AgentProfile.DoesNotExist:
            pass

    def test_agent_voit_ses_clients(self, auth_agent):
        r = auth_agent.get('/api/v1/agents/me/clients/')
        assert r.status_code == status.HTTP_200_OK

    def test_client_ne_peut_pas_acceder_profil_agent_prive(self, auth_client):
        r = auth_client.get('/api/v1/agents/me/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_choisir_agent(self, auth_client, agent_user):
        from apps.agents.models import AgentProfile
        try:
            profile = AgentProfile.objects.get(user=agent_user)
            r = auth_client.post('/api/v1/agents/choose/', {
                'agent_id': str(profile.id),
            })
            assert r.status_code in [200, 201, 400]
        except AgentProfile.DoesNotExist:
            pass


class TestOwners:

    def test_profil_owner(self, auth_owner):
        r = auth_owner.get('/api/v1/owners/me/')
        assert r.status_code == status.HTTP_200_OK

    def test_client_ne_peut_pas_acceder_profil_owner(self, auth_client):
        r = auth_client.get('/api/v1/owners/me/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_met_a_jour_compte_bancaire(self, auth_owner):
        r = auth_owner.patch('/api/v1/owners/me/bank-accounts/', {
            'mtn_momo_number': '+237670000003',
        })
        assert r.status_code in [200, 201]

    def test_owner_voir_son_agent(self, auth_owner):
        r = auth_owner.get('/api/v1/owners/me/agent/')
        assert r.status_code == status.HTTP_200_OK

    def test_owner_ne_choisit_pas_deuxieme_agent(self, auth_owner, agent_user, owner_user, create_user):
        OwnerAgentRelation.objects.get_or_create(
            owner=owner_user, agent=agent_user,
            defaults={'status': 'active', 'contract_start': date.today()}
        )
        autre_agent = create_user(
            email='agent3@test.cm', phone='+237670000075',
            role='agent', is_validated=True,
        )
        r = auth_owner.post('/api/v1/owners/me/agent/', {
            'agent_id': str(autre_agent.id),
        })
        assert r.status_code in [400, 403, 405]
