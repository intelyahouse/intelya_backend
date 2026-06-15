import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestOwnerProfile:

    def test_get_owner_profile(self, auth_owner):
        response = auth_owner.get('/api/v1/owners/me/')
        assert response.status_code == status.HTTP_200_OK

    def test_client_cannot_access_owner_profile(self, auth_client):
        response = auth_client.get('/api/v1/owners/me/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_bank_accounts(self, auth_owner):
        response = auth_owner.patch('/api/v1/owners/me/bank-accounts/', {
            'mtn_momo_number': '+237670000200',
            'orange_money_number': '+237690000200',
        })
        assert response.status_code == status.HTTP_200_OK

    def test_choose_agent(self, auth_owner, agent_user):
        from apps.agents.models import AgentProfile
        profile = AgentProfile.objects.get(user=agent_user)
        response = auth_owner.post('/api/v1/owners/me/agent/', {
            'agent_id': str(profile.id),
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_cannot_choose_second_agent(self, auth_owner, agent_user, create_user):
        from apps.agents.models import AgentProfile
        profile1 = AgentProfile.objects.get(user=agent_user)
        auth_owner.post('/api/v1/owners/me/agent/', {'agent_id': str(profile1.id)})

        agent2 = create_user(email='agent2_owner@test.com', phone='+237670000201', role='agent', is_validated=True)
        AgentProfile.objects.create(user=agent2, working_city='Yaoundé')
        profile2 = AgentProfile.objects.get(user=agent2)
        response = auth_owner.post('/api/v1/owners/me/agent/', {'agent_id': str(profile2.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
