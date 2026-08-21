"""
Regression pour une vraie vulnerabilite trouvee par revue de securite :
un client qui s'auto-declare 'agent' via /auth/request-role/ (role change
immediatement, is_validated reste False, donc AUCUN AgentProfile/Agency
n'existe pour lui) ne doit JAMAIS recevoir les baux/paiements/plaintes
"sans agence" de TOUTE la plateforme. Avant le correctif,
`agency_id = getattr(..., None)` valait None, et
`.filter(agency_id=agency_id)` se traduisait en `WHERE agency_id IS NULL`,
exposant les donnees de n'importe quel tenant agentless a n'importe quel
faux "agent" non valide.
"""
import datetime
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.contracts.models import LeaseContract
from apps.leases.models import RentPayment, Complaint

pytestmark = pytest.mark.django_db


def _fake_pending_agent(create_user, email, phone):
    """Un utilisateur qui a demande le role agent mais n'est pas valide --
    role='agent' des la demande (comportement voulu), mais sans
    AgentProfile/Agency (cree uniquement a la validation admin)."""
    user = create_user(email=email, phone=phone, role='client', is_validated=False)
    user.role = 'agent'
    user.validation_status = 'pending'
    user.save(update_fields=['role', 'validation_status'])
    return user


def _agentless_lease(owner_user, tenant_user, property_obj):
    return LeaseContract.objects.create(
        tenant=tenant_user, owner=owner_user, agent=None, agency=None,
        rental_property=property_obj, monthly_rent=30000, deposit_amount=60000,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=365),
        payment_day=5, status='active', signed_by_tenant=True, signed_by_owner=True,
    )


class TestUnvalidatedFakeAgentCannotSeeOthersData:

    def test_cannot_list_agentless_leases(self, create_user, owner_user, client_user, property_obj):
        _agentless_lease(owner_user, client_user, property_obj)
        fake_agent = _fake_pending_agent(create_user, 'fake_agent_leases@test.com', '+237670000800')
        client = APIClient()
        client.force_authenticate(user=fake_agent)

        r = client.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['data'] == []

    def test_cannot_list_agentless_rent_payments(self, create_user, owner_user, client_user, property_obj):
        lease = _agentless_lease(owner_user, client_user, property_obj)
        RentPayment.objects.create(
            lease=lease, tenant=client_user, amount=30000, status='pending',
            due_date=datetime.date.today(),
            period_month=datetime.date.today().month, period_year=datetime.date.today().year,
        )
        fake_agent = _fake_pending_agent(create_user, 'fake_agent_payments@test.com', '+237670000801')
        client = APIClient()
        client.force_authenticate(user=fake_agent)

        r = client.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['results'] == []

    def test_cannot_list_agentless_complaints(self, create_user, owner_user, client_user, property_obj):
        lease = _agentless_lease(owner_user, client_user, property_obj)
        Complaint.objects.create(
            lease=lease, tenant=client_user, category='maintenance',
            title='Fuite', description="Il y a une fuite dans la cuisine, tres genant au quotidien.",
            status='open', assigned_to=owner_user,
        )
        fake_agent = _fake_pending_agent(create_user, 'fake_agent_complaints@test.com', '+237670000802')
        client = APIClient()
        client.force_authenticate(user=fake_agent)

        r = client.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['results'] == []

    def test_real_validated_agent_still_sees_own_agency_data(
        self, auth_agent, agent_user, owner_user, client_with_agent, property_obj
    ):
        """Non-regression : un vrai agent valide continue de voir les
        baux/paiements/plaintes de sa propre agence normalement."""
        from apps.agents.models import AgentProfile
        profile = AgentProfile.objects.get(user=agent_user)
        lease = LeaseContract.objects.create(
            tenant=client_with_agent, owner=owner_user, agent=agent_user, agency=profile.agency,
            rental_property=property_obj, monthly_rent=30000, deposit_amount=60000,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=365),
            payment_day=5, status='active', signed_by_tenant=True, signed_by_owner=True,
        )
        r = auth_agent.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data['data']) == 1
        assert r.data['data'][0]['id'] == str(lease.id)
