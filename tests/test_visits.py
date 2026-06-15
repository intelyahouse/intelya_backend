import pytest
from rest_framework import status
from apps.visits.models import VisitRequest
from apps.agents.models import ClientAgentRelation

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_with_agent(client_user, agent_user):
    ClientAgentRelation.objects.create(client=client_user, agent=agent_user, is_active=True)
    return client_user


class TestRequestVisit:

    def test_request_visit_success(self, api_client, client_with_agent, property_obj):
        api_client.force_authenticate(user=client_with_agent)
        response = api_client.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
            'client_message': 'Je suis disponible en semaine',
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert VisitRequest.objects.filter(
            client=client_with_agent, visit_property=property_obj
        ).exists()

    def test_request_visit_without_agent_fails(self, auth_client, property_obj):
        response = auth_client.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_request_visit_unauthenticated_fails(self, api_client, property_obj):
        response = api_client.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_duplicate_visit_request_fails(self, api_client, client_with_agent, property_obj):
        api_client.force_authenticate(user=client_with_agent)
        api_client.post('/api/v1/visits/request/', {'property_id': str(property_obj.id)})
        response = api_client.post('/api/v1/visits/request/', {'property_id': str(property_obj.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_owner_cannot_request_visit(self, auth_owner, property_obj):
        response = auth_owner.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestScheduleVisit:

    @pytest.fixture
    def pending_visit(self, client_user, agent_user, property_obj):
        ClientAgentRelation.objects.get_or_create(client=client_user, agent=agent_user)
        return VisitRequest.objects.create(
            client=client_user,
            agent=agent_user,
            visit_property=property_obj,
            status='pending',
            is_free=True,
            payment_status='not_required',
        )

    def test_agent_can_schedule(self, auth_agent, pending_visit):
        response = auth_agent.post(f'/api/v1/visits/{pending_visit.id}/schedule/', {
            'scheduled_date': '2026-12-01',
            'scheduled_time': '10:00:00',
        })
        assert response.status_code == status.HTTP_200_OK
        pending_visit.refresh_from_db()
        assert pending_visit.status == 'scheduled'

    def test_client_cannot_schedule(self, auth_client, pending_visit):
        response = auth_client.post(f'/api/v1/visits/{pending_visit.id}/schedule/', {
            'scheduled_date': '2026-12-01',
            'scheduled_time': '10:00:00',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_wrong_agent_cannot_schedule(self, api_client, pending_visit, create_user):
        other_agent = create_user(
            email='other@agent.com', phone='+237670000060',
            role='agent', is_validated=True,
        )
        api_client.force_authenticate(user=other_agent)
        response = api_client.post(f'/api/v1/visits/{pending_visit.id}/schedule/', {
            'scheduled_date': '2026-12-01',
            'scheduled_time': '10:00:00',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCancelVisit:

    @pytest.fixture
    def scheduled_visit(self, client_user, agent_user, property_obj):
        ClientAgentRelation.objects.get_or_create(client=client_user, agent=agent_user)
        return VisitRequest.objects.create(
            client=client_user,
            agent=agent_user,
            visit_property=property_obj,
            status='scheduled',
            is_free=True,
        )

    def test_client_can_cancel_own_visit(self, api_client, scheduled_visit, client_user):
        api_client.force_authenticate(user=client_user)
        response = api_client.post(f'/api/v1/visits/{scheduled_visit.id}/cancel/', {
            'reason': 'Changement de planning',
        })
        assert response.status_code == status.HTTP_200_OK
        scheduled_visit.refresh_from_db()
        assert scheduled_visit.status == 'cancelled'

    def test_other_user_cannot_cancel(self, api_client, scheduled_visit, create_user):
        other_client = create_user(
            email='other_client@test.com', phone='+237670000070', role='client'
        )
        api_client.force_authenticate(user=other_client)
        response = api_client.post(f'/api/v1/visits/{scheduled_visit.id}/cancel/', {
            'reason': 'Tentative IDOR',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancel_without_reason_fails(self, api_client, scheduled_visit, client_user):
        api_client.force_authenticate(user=client_user)
        response = api_client.post(f'/api/v1/visits/{scheduled_visit.id}/cancel/', {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestMyVisits:

    def test_client_sees_own_visits(self, api_client, client_user, agent_user, property_obj):
        ClientAgentRelation.objects.get_or_create(client=client_user, agent=agent_user)
        VisitRequest.objects.create(
            client=client_user, agent=agent_user,
            visit_property=property_obj, status='pending',
        )
        api_client.force_authenticate(user=client_user)
        response = api_client.get('/api/v1/visits/')
        assert response.status_code == status.HTTP_200_OK

    def test_agent_sees_his_visits(self, auth_agent, agent_user, client_user, property_obj):
        ClientAgentRelation.objects.get_or_create(client=client_user, agent=agent_user)
        VisitRequest.objects.create(
            client=client_user, agent=agent_user,
            visit_property=property_obj, status='pending',
        )
        response = auth_agent.get('/api/v1/visits/')
        assert response.status_code == status.HTTP_200_OK
