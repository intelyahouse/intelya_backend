import pytest
from rest_framework import status
from apps.agents.models import AgentProfile, ClientAgentRelation

pytestmark = pytest.mark.django_db


class TestAgentList:

    def test_list_agents_public(self, api_client):
        response = api_client.get('/api/v1/agents/')
        assert response.status_code == status.HTTP_200_OK

    def test_list_agents_filter_by_city(self, api_client, agent_user):
        response = api_client.get('/api/v1/agents/?city=Douala')
        assert response.status_code == status.HTTP_200_OK

    def test_agent_public_profile(self, api_client, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        response = api_client.get(f'/api/v1/agents/{profile.id}/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'full_name' in data
        assert 'reliability_score' in data

    def test_agent_profile_not_found(self, api_client):
        import uuid
        response = api_client.get(f'/api/v1/agents/{uuid.uuid4()}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgentProfile:

    def test_get_my_agent_profile(self, auth_agent, agent_user):
        response = auth_agent.get('/api/v1/agents/me/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['full_name'] == agent_user.get_full_name()

    def test_client_cannot_access_agent_profile(self, auth_client):
        response = auth_client.get('/api/v1/agents/me/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_agent_profile(self, auth_agent, agent_user):
        response = auth_agent.patch('/api/v1/agents/me/', {
            'agency_name': 'Agence INTELYA Test',
            'bio': 'Agent professionnel avec 5 ans d expérience',
        })
        assert response.status_code == status.HTTP_200_OK
        profile = AgentProfile.objects.get(user=agent_user)
        assert profile.agency_name == 'Agence INTELYA Test'
        assert profile.agency.name == 'Agence INTELYA Test'


class TestChooseAgent:

    def test_client_can_choose_agent(self, auth_client, agent_user, client_user):
        profile = AgentProfile.objects.get(user=agent_user)
        response = auth_client.post('/api/v1/agents/choose/', {
            'agent_id': str(profile.id),
        })
        assert response.status_code == status.HTTP_200_OK
        assert ClientAgentRelation.objects.filter(
            client=client_user, agent=agent_user, is_active=True
        ).exists()

    def test_client_cannot_choose_second_agent(self, auth_client, agent_user, client_user, create_user):
        agent2 = create_user(
            email='agent2@test.com', phone='+237670000050',
            role='agent', is_validated=True,
        )
        from apps.agents.services import ensure_agent_profile_and_agency
        ensure_agent_profile_and_agency(agent2, working_city_default='Yaoundé')
        profile1 = AgentProfile.objects.get(user=agent_user)
        profile2 = AgentProfile.objects.get(user=agent2)
        auth_client.post('/api/v1/agents/choose/', {'agent_id': str(profile1.id)})
        response = auth_client.post('/api/v1/agents/choose/', {'agent_id': str(profile2.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_agent_sees_his_clients(self, auth_agent, agent_user, client_user):
        profile = AgentProfile.objects.get(user=agent_user)
        ClientAgentRelation.objects.create(client=client_user, agent=agent_user, agency=profile.agency)
        response = auth_agent.get('/api/v1/agents/me/clients/')
        assert response.status_code == status.HTTP_200_OK


class TestAgentAvailability:

    def test_add_availability_slot(self, auth_agent):
        response = auth_agent.post('/api/v1/agents/me/availability/', {
            'day_of_week': 1,
            'start_time': '09:00:00',
            'end_time': '12:00:00',
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_get_availability_slots(self, auth_agent):
        response = auth_agent.get('/api/v1/agents/me/availability/')
        assert response.status_code == status.HTTP_200_OK

    def test_client_cannot_add_slots(self, auth_client):
        response = auth_client.post('/api/v1/agents/me/availability/', {
            'day_of_week': 1,
            'start_time': '09:00:00',
            'end_time': '12:00:00',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
