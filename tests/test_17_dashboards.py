import datetime
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile, ClientAgentRelation, OwnerAgentRelation
from apps.contracts.models import LeaseContract
from apps.leases.models import RentPayment

pytestmark = pytest.mark.django_db


class TestTenantDashboard:

    def test_no_agency_no_lease(self, auth_client):
        r = auth_client.get('/api/v1/leases/dashboard/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data['data']
        assert data['status']['has_agency'] is False
        assert data['status']['has_active_lease'] is False
        actions = {a['action']: a for a in data['available_actions']}
        assert actions['choose_agency']['available'] is True
        assert actions['contact_agency']['available'] is False
        assert actions['pay_rent']['available'] is False

    def test_with_agency_and_active_lease_pending_payment(
        self, auth_client_with_agent, client_with_agent, agent_user, owner_user, property_obj
    ):
        profile = AgentProfile.objects.get(user=agent_user)
        lease = LeaseContract.objects.create(
            tenant=client_with_agent, owner=owner_user, agent=agent_user, agency=profile.agency,
            rental_property=property_obj, monthly_rent=30000, deposit_amount=60000,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=365),
            payment_day=5, status='active', signed_by_tenant=True, signed_by_owner=True,
        )
        RentPayment.objects.create(
            lease=lease, tenant=client_with_agent, amount=30000,
            due_date=datetime.date.today(), status='pending',
            period_month=datetime.date.today().month, period_year=datetime.date.today().year,
        )

        r = auth_client_with_agent.get('/api/v1/leases/dashboard/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data['data']
        assert data['status']['has_agency'] is True
        assert data['status']['has_active_lease'] is True
        actions = {a['action']: a for a in data['available_actions']}
        assert actions['pay_rent']['available'] is True
        assert actions['choose_agency']['available'] is False
        assert actions['contact_agency']['available'] is True

    def test_unauthenticated_blocked(self, api_client):
        r = api_client.get('/api/v1/leases/dashboard/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_agent_cannot_access(self, auth_agent):
        r = auth_agent.get('/api/v1/leases/dashboard/')
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestAgencyDashboard:

    def test_gerant_sees_gerant_actions(self, auth_agent, agent_user):
        r = auth_agent.get('/api/v1/agencies/me/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data['data']
        assert data['is_gerant'] is True
        actions = {a['action']: a for a in data['available_actions']}
        assert actions['manage_agents']['available'] is True
        assert actions['leave_agency']['available'] is False

    def test_regular_member_sees_restricted_actions(self, agent_user, create_user):
        from apps.agents.services import ensure_agent_profile_and_agency
        from apps.agencies.services import transfer_agent_to_agency
        member = create_user(email='dash_member@test.com', phone='+237670000500', role='agent', is_validated=True)
        ensure_agent_profile_and_agency(member)
        member_profile = AgentProfile.objects.get(user=member)
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        transfer_agent_to_agency(member_profile, gerant_profile.agency)

        from django.contrib.auth import get_user_model
        member = get_user_model().objects.get(pk=member.pk)

        from rest_framework.test import APIClient
        auth_member = APIClient()
        auth_member.force_authenticate(user=member)
        r = auth_member.get('/api/v1/agencies/me/')
        data = r.data['data']
        assert data['is_gerant'] is False
        actions = {a['action']: a for a in data['available_actions']}
        assert actions['manage_agents']['available'] is False
        assert actions['leave_agency']['available'] is True
        assert actions['manage_clients']['available'] is True

    def test_has_payment_info_flag(self, auth_agent, agent_user):
        r = auth_agent.get('/api/v1/agencies/me/')
        assert r.data['data']['has_payment_info'] is False

        profile = AgentProfile.objects.get(user=agent_user)
        profile.agency.mtn_momo_number = '+237670000001'
        profile.agency.save(update_fields=['mtn_momo_number'])

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        fresh_agent = get_user_model().objects.get(pk=agent_user.pk)
        auth_agent_2 = APIClient()
        auth_agent_2.force_authenticate(user=fresh_agent)

        r = auth_agent_2.get('/api/v1/agencies/me/')
        assert r.data['data']['has_payment_info'] is True


class TestOwnerDashboard:

    def test_no_agency_not_validated(self, auth_client, create_user):
        from rest_framework.test import APIClient
        owner = create_user(email='dash_owner1@test.com', phone='+237670000501', role='owner', is_validated=False)
        auth_owner = APIClient()
        auth_owner.force_authenticate(user=owner)

        r = auth_owner.get('/api/v1/owners/me/dashboard/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data['data']
        assert data['status']['is_validated'] is False
        actions = {a['action']: a for a in data['available_actions']}
        assert actions['add_property']['available'] is False
        assert actions['choose_agency']['available'] is True

    def test_with_active_agency_relation(self, owner_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency, status='active',
            contract_start=datetime.date.today(),
        )
        from rest_framework.test import APIClient
        auth_owner = APIClient()
        auth_owner.force_authenticate(user=owner_user)

        r = auth_owner.get('/api/v1/owners/me/dashboard/')
        data = r.data['data']
        assert data['status']['has_active_agency'] is True
        assert data['status']['agency_name'] is not None
        actions = {a['action']: a for a in data['available_actions']}
        assert actions['choose_agency']['available'] is False
        assert actions['terminate_mandate']['available'] is True

    def test_unauthenticated_blocked(self, api_client):
        r = api_client.get('/api/v1/owners/me/dashboard/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
