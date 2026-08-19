import pytest
from apps.agents.models import AgentProfile
from apps.agencies.models import Agency
from apps.agents.services import ensure_agent_profile_and_agency

pytestmark = pytest.mark.django_db


class TestAgencyAutoCreation:

    def test_new_validated_agent_gets_solo_agency(self, create_user):
        user = create_user(
            email="agent_auto@test.com", phone="+237670000060",
            role="agent", is_validated=True,
        )
        profile = AgentProfile.objects.get(user=user)
        assert profile.agency_id is not None
        assert profile.agency.owner_agent == user
        assert profile.agency.is_solo is True

    def test_admin_validation_flow_creates_agency(self, create_user, admin_user, api_client):
        applicant = create_user(
            email="agent_pending@test.com", phone="+237670000061",
            role="agent", is_validated=False,
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            f'/api/v1/admin-panel/users/{applicant.id}/validate/',
            {'action': 'approve'},
        )
        assert response.status_code == 200
        profile = AgentProfile.objects.get(user=applicant)
        assert profile.agency_id is not None
        assert profile.agency.owner_agent == applicant

    def test_ensure_agent_profile_and_agency_is_idempotent(self, agent_user):
        profile_before = AgentProfile.objects.get(user=agent_user)
        agency_id_before = profile_before.agency_id

        ensure_agent_profile_and_agency(agent_user)

        profile_after = AgentProfile.objects.get(user=agent_user)
        assert profile_after.agency_id == agency_id_before
        assert Agency.objects.filter(owner_agent=agent_user).count() == 1

    def test_default_agency_name_derived_from_full_name(self, create_user):
        user = create_user(
            email="agent_noname@test.com", phone="+237670000062",
            role="agent", is_validated=True,
            first_name="Jean", last_name="Kamga",
        )
        profile = AgentProfile.objects.get(user=user)
        assert profile.agency.name == "Agence de Jean Kamga"
