import datetime
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile, ClientAgentRelation
from apps.agencies.services import transfer_agent_to_agency

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_agent(create_user):
    return create_user(
        email="agent2@test.com", phone="+237670000090",
        role="agent", is_validated=True,
    )


@pytest.fixture
def auth_agent2(second_agent):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=second_agent)
    return client


def _join_agency(agent_user, colleague):
    gerant_agency = AgentProfile.objects.get(user=agent_user).agency
    transfer_agent_to_agency(AgentProfile.objects.get(user=colleague), gerant_agency)
    return gerant_agency


def _make_relation(client_user, agent_user):
    profile = AgentProfile.objects.get(user=agent_user)
    return ClientAgentRelation.objects.create(
        client=client_user, agent=agent_user, agency=profile.agency, is_active=True,
    )


def _publishable_property(**kwargs):
    """Cree un bien respectant le minimum de publication (4 photos + video
    >= 1 minute) pour qu'il soit visible dans les tests d'exclusivite."""
    import io
    from PIL import Image
    from django.core.files.base import ContentFile
    from apps.properties.models import Property, PropertyPhoto, PropertyVideo

    prop = Property.objects.create(**kwargs)
    for i in range(4):
        buf = io.BytesIO()
        Image.new('RGB', (100, 100)).save(buf, format='JPEG')
        PropertyPhoto.objects.create(property=prop, photo=ContentFile(buf.getvalue(), name=f'p{i}.jpg'))
    PropertyVideo.objects.create(property=prop, duration_seconds=90)
    return prop


class TestChooseAndLeaveAgent:

    def test_choose_agent_sets_agency(self, auth_client, client_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        response = auth_client.post('/api/v1/agents/choose/', {'agent_id': str(profile.id)})
        assert response.status_code == status.HTTP_200_OK

        relation = ClientAgentRelation.objects.get(client=client_user, agent=agent_user)
        assert relation.agency_id == profile.agency_id

    def test_client_can_leave_agent_and_choose_new_one(
        self, auth_client, client_user, agent_user, second_agent
    ):
        relation = _make_relation(client_user, agent_user)

        response = auth_client.delete('/api/v1/agents/choose/', {'reason': 'Pas satisfait'})
        assert response.status_code == status.HTTP_200_OK

        relation.refresh_from_db()
        assert relation.is_active is False
        assert relation.termination_reason == 'Pas satisfait'
        assert relation.terminated_at is not None

        second_profile = AgentProfile.objects.get(user=second_agent)
        response2 = auth_client.post('/api/v1/agents/choose/', {'agent_id': str(second_profile.id)})
        assert response2.status_code == status.HTTP_200_OK
        assert ClientAgentRelation.objects.filter(
            client=client_user, agent=second_agent, is_active=True
        ).exists()

    def test_leave_without_reason_fails(self, auth_client, client_user, agent_user):
        _make_relation(client_user, agent_user)
        response = auth_client.delete('/api/v1/agents/choose/', {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAgencyWideClientAccess:

    def test_colleague_sees_client_in_agency_list(
        self, auth_agent2, agent_user, second_agent, client_user
    ):
        _join_agency(agent_user, second_agent)
        _make_relation(client_user, agent_user)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.get('/api/v1/agents/me/clients/')
        assert response.status_code == status.HTTP_200_OK
        client_ids = [c['id'] for c in response.data['data']]
        assert str(client_user.id) in client_ids

    def test_outsider_does_not_see_client(self, auth_agent2, agent_user, second_agent, client_user):
        _make_relation(client_user, agent_user)
        response = auth_agent2.get('/api/v1/agents/me/clients/')
        assert response.status_code == status.HTTP_200_OK
        client_ids = [c['id'] for c in response.data['data']]
        assert str(client_user.id) not in client_ids

    def test_colleague_can_create_lease_for_client(
        self, auth_agent2, agent_user, second_agent, client_user, owner_user, property_obj
    ):
        _join_agency(agent_user, second_agent)
        _make_relation(client_user, agent_user)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post('/api/v1/contracts/leases/create/', {
            'tenant': str(client_user.id),
            'owner': str(owner_user.id),
            'rental_property': str(property_obj.id),
            'monthly_rent': 100000,
            'deposit_amount': 100000,
            'agent_commission': 10000,
            'commission_before_rent': True,
            'start_date': str(datetime.date.today()),
            'end_date': str(datetime.date.today() + datetime.timedelta(days=365)),
            'payment_day': 5,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_outsider_cannot_create_lease_for_client(
        self, auth_agent2, agent_user, second_agent, client_user, owner_user, property_obj
    ):
        _make_relation(client_user, agent_user)
        response = auth_agent2.post('/api/v1/contracts/leases/create/', {
            'tenant': str(client_user.id),
            'owner': str(owner_user.id),
            'rental_property': str(property_obj.id),
            'monthly_rent': 100000,
            'deposit_amount': 100000,
            'agent_commission': 10000,
            'commission_before_rent': True,
            'start_date': str(datetime.date.today()),
            'end_date': str(datetime.date.today() + datetime.timedelta(days=365)),
            'payment_day': 5,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestPropertyExclusivityByAgency:

    def test_client_sees_full_info_for_agency_property_from_colleague(
        self, auth_client, client_user, agent_user, second_agent, owner_user
    ):
        _join_agency(agent_user, second_agent)
        _make_relation(client_user, agent_user)

        prop = _publishable_property(
            owner=owner_user, agent=second_agent,
            title="Bien du collegue", description="x" * 300,
            property_type="apartment", price=100000, payment_period="monthly",
            city="Douala", neighborhood="Akwa", bedrooms=2, bathrooms=1,
            status="available",
        )
        response = auth_client.get(f'/api/v1/properties/{prop.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['belongs_to_other_agent'] is False

    def test_client_sees_masked_info_for_other_agency_property(
        self, auth_client, client_user, agent_user, second_agent, owner_user
    ):
        # second_agent garde sa propre agence solo (pas de _join_agency)
        _make_relation(client_user, agent_user)

        prop = _publishable_property(
            owner=owner_user, agent=second_agent,
            title="Bien d'une autre agence", description="x" * 300,
            property_type="apartment", price=100000, payment_period="monthly",
            city="Douala", neighborhood="Akwa", bedrooms=2, bathrooms=1,
            status="available",
        )
        response = auth_client.get(f'/api/v1/properties/{prop.id}/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['belongs_to_other_agent'] is True
        assert data['agent_name'] is None
        assert data['my_agent']['id'] == str(agent_user.id)


class TestMessagingAgencyWide:

    def test_client_can_message_colleague_in_same_agency(
        self, auth_client, client_user, agent_user, second_agent
    ):
        _join_agency(agent_user, second_agent)
        _make_relation(client_user, agent_user)

        response = auth_client.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(second_agent.id),
        })
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    def test_client_cannot_message_agent_outside_agency(
        self, auth_client, client_user, agent_user, second_agent
    ):
        _make_relation(client_user, agent_user)
        response = auth_client.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(second_agent.id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestClientReassign:

    def test_gerant_can_reassign_client(self, auth_agent, agent_user, second_agent, client_user):
        _join_agency(agent_user, second_agent)
        relation = _make_relation(client_user, agent_user)
        second_profile = AgentProfile.objects.get(user=second_agent)

        response = auth_agent.post(f'/api/v1/agencies/clients/{relation.id}/reassign/', {
            'agent_profile_id': str(second_profile.id),
        })
        assert response.status_code == status.HTTP_200_OK

        relation.refresh_from_db()
        assert relation.agent_id == second_agent.id

    def test_outsider_cannot_reassign_client(self, auth_agent2, agent_user, second_agent, client_user):
        relation = _make_relation(client_user, agent_user)
        response = auth_agent2.post(f'/api/v1/agencies/clients/{relation.id}/reassign/', {
            'agent_profile_id': str(AgentProfile.objects.get(user=second_agent).id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_reassign_client_to_agent_outside_agency(
        self, auth_agent, agent_user, second_agent, client_user
    ):
        relation = _make_relation(client_user, agent_user)
        second_profile = AgentProfile.objects.get(user=second_agent)
        response = auth_agent.post(f'/api/v1/agencies/clients/{relation.id}/reassign/', {
            'agent_profile_id': str(second_profile.id),
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND
