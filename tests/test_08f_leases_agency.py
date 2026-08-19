import datetime
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile
from apps.agencies.services import transfer_agent_to_agency
from apps.contracts.models import LeaseContract
from apps.leases.models import RentPayment, Complaint

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_agent(create_user):
    return create_user(
        email="agent2@test.com", phone="+237670000110",
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


@pytest.fixture
def bail_actif(agent_user, owner_user, client_with_agent, property_obj):
    return LeaseContract.objects.create(
        tenant=client_with_agent,
        owner=owner_user,
        agent=agent_user,
        agency=AgentProfile.objects.get(user=agent_user).agency,
        rental_property=property_obj,
        monthly_rent=150000,
        deposit_amount=300000,
        start_date=datetime.date.today() - datetime.timedelta(days=30),
        end_date=datetime.date.today() + datetime.timedelta(days=335),
        payment_day=5,
        status='active',
        signed_by_tenant=True,
        signed_by_owner=True,
    )


class TestAgencyWideLeaseVisibility:

    def test_colleague_sees_lease_in_my_leases(self, auth_agent2, agent_user, second_agent, bail_actif):
        _join_agency(agent_user, second_agent)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.get('/api/v1/contracts/leases/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 1

    def test_outsider_does_not_see_lease(self, auth_agent2, bail_actif):
        response = auth_agent2.get('/api/v1/contracts/leases/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 0


class TestAgencyWideCashConfirmation:

    def _make_payment(self, bail_actif, client_with_agent):
        return RentPayment.objects.create(
            lease=bail_actif, tenant=client_with_agent, amount=150000,
            status='pending', due_date=datetime.date.today(),
            period_month=datetime.date.today().month, period_year=datetime.date.today().year,
        )

    def test_colleague_can_confirm_cash_payment(
        self, auth_agent2, agent_user, second_agent, bail_actif, client_with_agent
    ):
        _join_agency(agent_user, second_agent)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)
        payment = self._make_payment(bail_actif, client_with_agent)

        response = auth_agent2.post('/api/v1/leases/payments/confirm-cash/', {
            'rent_payment_id': str(payment.id),
        })
        assert response.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.status == 'paid'

    def test_outsider_cannot_confirm_cash_payment(self, auth_agent2, bail_actif, client_with_agent):
        payment = self._make_payment(bail_actif, client_with_agent)
        response = auth_agent2.post('/api/v1/leases/payments/confirm-cash/', {
            'rent_payment_id': str(payment.id),
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgencyWideDebtManagement:

    def _make_payment(self, bail_actif, client_with_agent):
        return RentPayment.objects.create(
            lease=bail_actif, tenant=client_with_agent, amount=150000,
            status='late', due_date=datetime.date.today() - datetime.timedelta(days=5),
            period_month=datetime.date.today().month, period_year=datetime.date.today().year,
        )

    def test_colleague_can_manage_debt(
        self, auth_agent2, agent_user, second_agent, bail_actif, client_with_agent
    ):
        _join_agency(agent_user, second_agent)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)
        payment = self._make_payment(bail_actif, client_with_agent)

        response = auth_agent2.post(f'/api/v1/leases/payments/{payment.id}/debt/', {
            'action': 'claim',
        })
        assert response.status_code == status.HTTP_200_OK

    def test_outsider_cannot_manage_debt(self, auth_agent2, bail_actif, client_with_agent):
        payment = self._make_payment(bail_actif, client_with_agent)
        response = auth_agent2.post(f'/api/v1/leases/payments/{payment.id}/debt/', {
            'action': 'claim',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgencyWideComplaints:

    def test_colleague_sees_complaint_not_personally_assigned(
        self, auth_agent2, agent_user, second_agent, bail_actif, client_with_agent
    ):
        _join_agency(agent_user, second_agent)
        Complaint.objects.create(
            lease=bail_actif, tenant=client_with_agent, assigned_to=agent_user,
            agency=bail_actif.agency, category='maintenance',
            title='Fuite', description='Une fuite dans la cuisine', status='open',
        )
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.get('/api/v1/leases/complaints/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_colleague_can_resolve_complaint_assigned_to_agent_colleague(
        self, auth_agent2, agent_user, second_agent, bail_actif, client_with_agent
    ):
        _join_agency(agent_user, second_agent)
        complaint = Complaint.objects.create(
            lease=bail_actif, tenant=client_with_agent, assigned_to=agent_user,
            agency=bail_actif.agency, category='maintenance',
            title='Fuite', description='Une fuite dans la cuisine', status='open',
        )
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post(f'/api/v1/leases/complaints/{complaint.id}/resolve/', {
            'resolution_note': 'Reparee par le plombier',
        })
        assert response.status_code == status.HTTP_200_OK
        complaint.refresh_from_db()
        assert complaint.status == 'resolved'

    def test_outsider_cannot_resolve_complaint(self, auth_agent2, agent_user, bail_actif, client_with_agent):
        complaint = Complaint.objects.create(
            lease=bail_actif, tenant=client_with_agent, assigned_to=agent_user,
            agency=bail_actif.agency, category='maintenance',
            title='Fuite', description='Une fuite dans la cuisine', status='open',
        )
        response = auth_agent2.post(f'/api/v1/leases/complaints/{complaint.id}/resolve/', {
            'resolution_note': 'Je ne devrais pas pouvoir',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_colleague_cannot_resolve_complaint_assigned_to_owner(
        self, auth_agent2, agent_user, second_agent, bail_actif, client_with_agent, owner_user
    ):
        _join_agency(agent_user, second_agent)
        complaint = Complaint.objects.create(
            lease=bail_actif, tenant=client_with_agent, assigned_to=owner_user,
            agency=bail_actif.agency, category='maintenance',
            title='Fuite', description='Une fuite dans la cuisine', status='open',
        )
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post(f'/api/v1/leases/complaints/{complaint.id}/resolve/', {
            'resolution_note': 'Pas mon role',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND
