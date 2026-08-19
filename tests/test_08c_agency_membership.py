import pytest
from rest_framework import status
from apps.agents.models import AgentProfile
from apps.agencies.models import Agency, AgencyInvitation

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_agent(create_user):
    return create_user(
        email="agent2@test.com", phone="+237670000070",
        role="agent", is_validated=True,
    )


@pytest.fixture
def auth_agent2(second_agent):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=second_agent)
    return client


class TestAgencyMe:

    def test_get_my_solo_agency(self, auth_agent, agent_user):
        response = auth_agent.get('/api/v1/agencies/me/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['is_solo'] is True
        assert data['owner_agent_id'] == str(agent_user.id)
        assert data['member_count'] == 1


class TestAgencyInvite:

    def test_gerant_can_invite_solo_agent(self, auth_agent, agent_user, second_agent):
        target_profile = AgentProfile.objects.get(user=second_agent)
        response = auth_agent.post('/api/v1/agencies/me/invite/', {
            'agent_profile_id': str(target_profile.id),
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert AgencyInvitation.objects.filter(
            invited_user=second_agent, invited_by=agent_user, status='pending'
        ).exists()

    def test_cannot_invite_self(self, auth_agent, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        response = auth_agent.post('/api/v1/agencies/me/invite/', {
            'agent_profile_id': str(profile.id),
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_double_invite_same_agent(self, auth_agent, agent_user, second_agent):
        target_profile = AgentProfile.objects.get(user=second_agent)
        auth_agent.post('/api/v1/agencies/me/invite/', {'agent_profile_id': str(target_profile.id)})
        response = auth_agent.post('/api/v1/agencies/me/invite/', {'agent_profile_id': str(target_profile.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_gerant_member_cannot_invite(self, auth_agent, auth_agent2, agent_user, second_agent, create_user):
        # second_agent rejoint l'agence de agent_user (devient membre, pas gerant)
        gerant_agency = AgentProfile.objects.get(user=agent_user).agency
        from apps.agencies.services import transfer_agent_to_agency
        transfer_agent_to_agency(AgentProfile.objects.get(user=second_agent), gerant_agency)

        third_agent = create_user(email="agent3@test.com", phone="+237670000071", role="agent", is_validated=True)
        third_profile = AgentProfile.objects.get(user=third_agent)

        # force_authenticate garde le meme objet Python second_agent en memoire :
        # sa relation inversee agent_profile a ete mise en cache au moment de sa
        # creation (signal). refresh_from_db() vide ce cache pour refleter le
        # transfert d'agence fait plus haut directement via le service.
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post('/api/v1/agencies/me/invite/', {
            'agent_profile_id': str(third_profile.id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAgencyInvitationResponse:

    def _create_invitation(self, agent_user, second_agent):
        agency = AgentProfile.objects.get(user=agent_user).agency
        return AgencyInvitation.objects.create(
            agency=agency, invited_user=second_agent, invited_by=agent_user,
        )

    def test_accept_invitation_moves_agent_and_updates_is_solo(self, auth_agent2, agent_user, second_agent):
        invitation = self._create_invitation(agent_user, second_agent)
        gerant_agency = AgentProfile.objects.get(user=agent_user).agency
        old_agency_id = AgentProfile.objects.get(user=second_agent).agency_id

        response = auth_agent2.post(f'/api/v1/agencies/invitations/{invitation.id}/respond/', {
            'action': 'accept',
        })
        assert response.status_code == status.HTTP_200_OK

        second_profile = AgentProfile.objects.get(user=second_agent)
        assert second_profile.agency_id == gerant_agency.id

        gerant_agency.refresh_from_db()
        assert gerant_agency.is_solo is False
        assert gerant_agency.agents.count() == 2

        old_agency = Agency.objects.get(id=old_agency_id)
        assert old_agency.is_solo is True

        invitation.refresh_from_db()
        assert invitation.status == 'accepted'

    def test_decline_invitation_does_not_move_agent(self, auth_agent2, agent_user, second_agent):
        invitation = self._create_invitation(agent_user, second_agent)
        old_agency_id = AgentProfile.objects.get(user=second_agent).agency_id

        response = auth_agent2.post(f'/api/v1/agencies/invitations/{invitation.id}/respond/', {
            'action': 'decline',
        })
        assert response.status_code == status.HTTP_200_OK

        second_profile = AgentProfile.objects.get(user=second_agent)
        assert second_profile.agency_id == old_agency_id
        invitation.refresh_from_db()
        assert invitation.status == 'declined'

    def test_cannot_respond_to_someone_elses_invitation(self, auth_agent, agent_user, second_agent, create_user, api_client):
        invitation = self._create_invitation(agent_user, second_agent)
        response = auth_agent.post(f'/api/v1/agencies/invitations/{invitation.id}/respond/', {
            'action': 'accept',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_received_invitations_list(self, auth_agent2, agent_user, second_agent):
        self._create_invitation(agent_user, second_agent)
        response = auth_agent2.get('/api/v1/agencies/invitations/received/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 1


class TestAgencyMemberManagement:

    def _join(self, agent_user, second_agent):
        gerant_agency = AgentProfile.objects.get(user=agent_user).agency
        invitation = AgencyInvitation.objects.create(
            agency=gerant_agency, invited_user=second_agent, invited_by=agent_user,
        )
        from apps.agencies.services import transfer_agent_to_agency
        transfer_agent_to_agency(AgentProfile.objects.get(user=second_agent), gerant_agency)
        invitation.status = 'accepted'
        invitation.save()
        return gerant_agency

    def test_gerant_removes_member(self, auth_agent, agent_user, second_agent):
        agency = self._join(agent_user, second_agent)
        response = auth_agent.post(f'/api/v1/agencies/me/members/{second_agent.id}/remove/')
        assert response.status_code == status.HTTP_200_OK

        second_profile = AgentProfile.objects.get(user=second_agent)
        assert second_profile.agency_id != agency.id
        assert second_profile.agency.is_solo is True

        agency.refresh_from_db()
        assert agency.is_solo is True
        assert agency.agents.count() == 1

    def test_gerant_cannot_remove_self(self, auth_agent, agent_user):
        response = auth_agent.post(f'/api/v1/agencies/me/members/{agent_user.id}/remove/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_member_can_leave(self, auth_agent2, agent_user, second_agent):
        agency = self._join(agent_user, second_agent)
        # force_authenticate garde le meme objet Python : on rafraichit le cache
        # de sa relation agent_profile apres le transfert fait via le service.
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)
        response = auth_agent2.post('/api/v1/agencies/me/leave/')
        assert response.status_code == status.HTTP_200_OK

        second_profile = AgentProfile.objects.get(user=second_agent)
        assert second_profile.agency_id != agency.id

    def test_gerant_cannot_leave_own_agency(self, auth_agent, agent_user, second_agent):
        self._join(agent_user, second_agent)
        response = auth_agent.post('/api/v1/agencies/me/leave/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
