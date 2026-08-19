import datetime
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile, ClientAgentRelation
from apps.network.models import Collaboration

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_agent(create_user):
    return create_user(
        email="agent2@test.com", phone="+237670000100",
        role="agent", is_validated=True,
    )


@pytest.fixture
def auth_agent2(second_agent):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=second_agent)
    return client


def _link_client(client_user, agent, agency=None):
    profile = AgentProfile.objects.get(user=agent)
    return ClientAgentRelation.objects.create(
        client=client_user, agent=agent, agency=agency or profile.agency, is_active=True,
    )


class TestAgencySearch:

    def test_agent_can_search_agencies(self, auth_agent2, agent_user, second_agent):
        response = auth_agent2.get('/api/v1/network/agencies/')
        assert response.status_code == status.HTTP_200_OK
        ids = [a['id'] for a in response.data['data']]
        my_agency_id = str(AgentProfile.objects.get(user=second_agent).agency_id)
        other_agency_id = str(AgentProfile.objects.get(user=agent_user).agency_id)
        assert my_agency_id not in ids
        assert other_agency_id in ids

    def test_client_cannot_access_network(self, auth_client):
        response = auth_client.get('/api/v1/network/agencies/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_cannot_access_network(self, auth_owner):
        response = auth_owner.get('/api/v1/network/agencies/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCreateCollaboration:

    def test_propose_collaboration_on_other_agency_property(
        self, auth_agent2, agent_user, second_agent, property_obj
    ):
        response = auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data['data']
        assert data['total_amount'] == '200.00'
        assert len(data['proposals']) == 1

        collab = Collaboration.objects.get(property=property_obj)
        second_profile = AgentProfile.objects.get(user=second_agent)
        agent_profile = AgentProfile.objects.get(user=agent_user)
        assert collab.client_agency_id == second_profile.agency_id
        assert collab.property_agency_id == agent_profile.agency_id
        assert collab.status == 'proposed'

    def test_cannot_propose_on_own_agency_property(self, auth_agent, property_obj):
        response = auth_agent.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_amount_rejected(self, auth_agent2, property_obj):
        response = auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': 'not-a-number',
            'property_agency_amount': '100',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_negative_amount_rejected(self, auth_agent2, property_obj):
        response = auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '-50',
            'property_agency_amount': '100',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_with_linked_client(self, auth_agent2, second_agent, client_user, property_obj):
        _link_client(client_user, second_agent)
        response = auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_id': str(client_user.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['client_name'] == client_user.get_full_name()

    def test_with_unlinked_client_rejected(self, auth_agent2, client_user, property_obj):
        response = auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_id': str(client_user.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestMyCollaborations:

    def test_both_agencies_see_the_collaboration(
        self, auth_agent, auth_agent2, agent_user, second_agent, property_obj
    ):
        auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })

        r1 = auth_agent.get('/api/v1/network/collaborations/')
        r2 = auth_agent2.get('/api/v1/network/collaborations/')
        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK
        assert len(r1.data['data']) == 1
        assert len(r2.data['data']) == 1

    def test_outsider_does_not_see_it(self, auth_agent2, auth_agent, create_user, property_obj):
        auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        outsider = create_user(email="agent3@test.com", phone="+237670000101", role="agent", is_validated=True)
        from rest_framework.test import APIClient
        auth_outsider = APIClient()
        auth_outsider.force_authenticate(user=outsider)

        response = auth_outsider.get('/api/v1/network/collaborations/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 0


class TestRespondCollaboration:

    def _propose(self, auth_agent2, property_obj):
        r = auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        return r.data['data']['id'] if 'id' in r.data['data'] else Collaboration.objects.get(property=property_obj).id

    def test_property_agency_can_accept(self, auth_agent, auth_agent2, property_obj):
        self._propose(auth_agent2, property_obj)
        collab = Collaboration.objects.get(property=property_obj)

        response = auth_agent.post(f'/api/v1/network/collaborations/{collab.id}/respond/', {
            'action': 'accept',
        })
        assert response.status_code == status.HTTP_200_OK
        collab.refresh_from_db()
        assert collab.status == 'accepted'

    def test_cannot_respond_to_own_proposal(self, auth_agent2, property_obj):
        self._propose(auth_agent2, property_obj)
        collab = Collaboration.objects.get(property=property_obj)

        response = auth_agent2.post(f'/api/v1/network/collaborations/{collab.id}/respond/', {
            'action': 'accept',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_outsider_cannot_respond(self, auth_agent2, property_obj, create_user):
        self._propose(auth_agent2, property_obj)
        collab = Collaboration.objects.get(property=property_obj)

        outsider = create_user(email="agent4@test.com", phone="+237670000102", role="agent", is_validated=True)
        from rest_framework.test import APIClient
        auth_outsider = APIClient()
        auth_outsider.force_authenticate(user=outsider)

        response = auth_outsider.post(f'/api/v1/network/collaborations/{collab.id}/respond/', {
            'action': 'accept',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_property_agency_can_reject(self, auth_agent, auth_agent2, property_obj):
        self._propose(auth_agent2, property_obj)
        collab = Collaboration.objects.get(property=property_obj)

        response = auth_agent.post(f'/api/v1/network/collaborations/{collab.id}/respond/', {
            'action': 'reject',
        })
        assert response.status_code == status.HTTP_200_OK
        collab.refresh_from_db()
        assert collab.status == 'rejected'


class TestCounterPropose:

    def test_counter_propose_updates_amounts_and_history(self, auth_agent, auth_agent2, property_obj):
        auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        collab = Collaboration.objects.get(property=property_obj)

        response = auth_agent.post(f'/api/v1/network/collaborations/{collab.id}/counter-propose/', {
            'client_agency_amount': '80',
            'property_agency_amount': '120',
        })
        assert response.status_code == status.HTTP_200_OK

        collab.refresh_from_db()
        assert str(collab.client_agency_amount) == '80.00'
        assert str(collab.property_agency_amount) == '120.00'
        assert collab.status == 'proposed'
        assert collab.proposals.count() == 2

        agent_profile = AgentProfile.objects.get(user=collab.property_agency.owner_agent)
        assert collab.last_proposed_by_agency_id == agent_profile.agency_id

    def test_original_proposer_can_accept_after_counter(self, auth_agent, auth_agent2, property_obj):
        auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        collab = Collaboration.objects.get(property=property_obj)
        auth_agent.post(f'/api/v1/network/collaborations/{collab.id}/counter-propose/', {
            'client_agency_amount': '80',
            'property_agency_amount': '120',
        })

        response = auth_agent2.post(f'/api/v1/network/collaborations/{collab.id}/respond/', {
            'action': 'accept',
        })
        assert response.status_code == status.HTTP_200_OK
        collab.refresh_from_db()
        assert collab.status == 'accepted'


class TestCancelCollaboration:

    def test_either_party_can_cancel(self, auth_agent2, property_obj):
        auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        collab = Collaboration.objects.get(property=property_obj)

        response = auth_agent2.post(f'/api/v1/network/collaborations/{collab.id}/cancel/')
        assert response.status_code == status.HTTP_200_OK
        collab.refresh_from_db()
        assert collab.status == 'cancelled'

    def test_outsider_cannot_cancel(self, auth_agent2, property_obj, create_user):
        auth_agent2.post('/api/v1/network/collaborations/', {
            'property_id': str(property_obj.id),
            'client_agency_amount': '100',
            'property_agency_amount': '100',
        })
        collab = Collaboration.objects.get(property=property_obj)

        outsider = create_user(email="agent5@test.com", phone="+237670000103", role="agent", is_validated=True)
        from rest_framework.test import APIClient
        auth_outsider = APIClient()
        auth_outsider.force_authenticate(user=outsider)

        response = auth_outsider.post(f'/api/v1/network/collaborations/{collab.id}/cancel/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
