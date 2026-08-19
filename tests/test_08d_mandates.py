import datetime
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile, OwnerAgentRelation
from apps.agencies.services import transfer_agent_to_agency

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_agent(create_user):
    return create_user(
        email="agent2@test.com", phone="+237670000080",
        role="agent", is_validated=True,
    )


@pytest.fixture
def auth_agent2(second_agent):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=second_agent)
    return client


def _join_agency(agent_user, colleague):
    """colleague rejoint l'agence de agent_user (gerant)"""
    gerant_agency = AgentProfile.objects.get(user=agent_user).agency
    transfer_agent_to_agency(AgentProfile.objects.get(user=colleague), gerant_agency)
    return gerant_agency


class TestChooseAgentSetsAgency:

    def test_owner_choose_agent_sets_mandate_agency(self, auth_owner, owner_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        response = auth_owner.post('/api/v1/owners/me/agent/', {
            'agent_id': str(profile.id),
        })
        assert response.status_code == status.HTTP_201_CREATED

        relation = OwnerAgentRelation.objects.get(owner=owner_user, agent=agent_user)
        assert relation.agency_id == profile.agency_id

    def test_get_my_agent_includes_agency(self, auth_owner, owner_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency,
            status='active', contract_start=datetime.date.today(),
        )
        response = auth_owner.get('/api/v1/owners/me/agent/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['agency_id'] == str(profile.agency_id)


class TestAgencyWideAccess:

    def test_colleague_in_same_agency_can_create_property_for_owner(
        self, auth_agent2, agent_user, second_agent, owner_user
    ):
        _join_agency(agent_user, second_agent)
        profile = AgentProfile.objects.get(user=agent_user)
        OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency,
            status='active', contract_start=datetime.date.today(),
        )
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post('/api/v1/properties/create/', {
            'owner_id': str(owner_user.id),
            'title': 'Bel Appartement Colleague',
            'description': 'Belle description tres detaillee et suffisamment longue pour valider les cinquante mots minimum requis par la plateforme INTELYA HAVEN afin de garantir la qualite et la completude des annonces immobilieres publiees sur cette excellente plateforme immobiliere africaine innovante et moderne qui aide efficacement les proprietaires agents et locataires camerounais partout',
            'property_type': 'apartment',
            'price': 150000,
            'payment_period': 'monthly',
            'min_lease_months': 6,
            'bedrooms': 3, 'bathrooms': 2,
            'living_rooms': 1, 'kitchens': 1,
            'area_sqm': 120,
            'city': 'Douala', 'neighborhood': 'Bonanjo',
            'full_address': 'Rue Test 1, Bonanjo',
            'is_furnished': True,
            'has_generator': True, 'has_parking': True,
            'has_borehole': False, 'has_water_tank': True,
            'has_fence': True, 'has_security_guard': False,
            'has_air_conditioning': False, 'parking_spots': 1,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_agent_outside_agency_cannot_create_property_for_owner(
        self, auth_agent2, agent_user, second_agent, owner_user
    ):
        # second_agent garde sa propre agence solo (pas de _join_agency ici)
        profile = AgentProfile.objects.get(user=agent_user)
        OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency,
            status='active', contract_start=datetime.date.today(),
        )
        response = auth_agent2.post('/api/v1/properties/create/', {
            'owner_id': str(owner_user.id),
            'title': 'Ne devrait pas passer',
            'description': 'x' * 300,
            'property_type': 'apartment',
            'price': 150000,
            'payment_period': 'monthly',
            'city': 'Douala',
            'neighborhood': 'Bonanjo',
            'bedrooms': 2,
            'bathrooms': 1,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_agent_owners_view_shows_agency_wide_mandates(
        self, auth_agent2, agent_user, second_agent, owner_user
    ):
        _join_agency(agent_user, second_agent)
        profile = AgentProfile.objects.get(user=agent_user)
        OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency,
            status='active', contract_start=datetime.date.today(),
        )
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.get('/api/v1/agents/me/owners/')
        assert response.status_code == status.HTTP_200_OK
        owner_ids = [o['id'] for o in response.data['data']]
        assert str(owner_user.id) in owner_ids


class TestAgencyWidePropertyManagement:

    def test_colleague_can_edit_property_published_by_agent(
        self, auth_agent2, agent_user, second_agent, property_obj
    ):
        _join_agency(agent_user, second_agent)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.patch(f'/api/v1/properties/{property_obj.id}/update/', {
            'price': 175000,
        })
        assert response.status_code == status.HTTP_200_OK
        property_obj.refresh_from_db()
        assert int(property_obj.price) == 175000

    def test_outsider_cannot_edit_property(self, auth_agent2, second_agent, property_obj):
        # second_agent garde sa propre agence solo
        response = auth_agent2.patch(f'/api/v1/properties/{property_obj.id}/update/', {
            'price': 999999,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def _fake_photo(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = io.BytesIO()
        Image.new('RGB', (100, 100)).save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile('photo.jpg', buf.read(), content_type='image/jpeg')

    def test_colleague_can_upload_photos(self, auth_agent2, agent_user, second_agent, property_obj):
        _join_agency(agent_user, second_agent)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post(
            f'/api/v1/properties/{property_obj.id}/photos/',
            {'photos': [self._fake_photo()]}, format='multipart'
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    def test_outsider_cannot_upload_photos(self, auth_agent2, second_agent, property_obj):
        response = auth_agent2.post(
            f'/api/v1/properties/{property_obj.id}/photos/',
            {'photos': [self._fake_photo()]}, format='multipart'
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgencyWideMessagingOwner:

    def _make_relation(self, agent_user, owner_user):
        profile = AgentProfile.objects.get(user=agent_user)
        return OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency,
            status='active', contract_start=datetime.date.today(),
        )

    def test_agent_colleague_can_message_owner(
        self, auth_agent2, agent_user, second_agent, owner_user
    ):
        _join_agency(agent_user, second_agent)
        self._make_relation(agent_user, owner_user)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(owner_user.id),
        })
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    def test_owner_can_message_agent_colleague(
        self, auth_owner, agent_user, second_agent, owner_user
    ):
        _join_agency(agent_user, second_agent)
        self._make_relation(agent_user, owner_user)

        response = auth_owner.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(second_agent.id),
        })
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    def test_owner_cannot_message_agent_outside_agency(
        self, auth_owner, agent_user, second_agent, owner_user
    ):
        self._make_relation(agent_user, owner_user)
        response = auth_owner.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(second_agent.id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestMandateReassign:

    def _make_relation(self, agent_user, owner_user):
        profile = AgentProfile.objects.get(user=agent_user)
        return OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency,
            status='active', contract_start=datetime.date.today(),
        )

    def test_gerant_can_reassign_mandate(self, auth_agent, agent_user, second_agent, owner_user):
        _join_agency(agent_user, second_agent)
        relation = self._make_relation(agent_user, owner_user)
        second_profile = AgentProfile.objects.get(user=second_agent)

        response = auth_agent.post(f'/api/v1/agencies/mandates/{relation.id}/reassign/', {
            'agent_profile_id': str(second_profile.id),
        })
        assert response.status_code == status.HTTP_200_OK

        relation.refresh_from_db()
        assert relation.agent_id == second_agent.id
        assert relation.agency_id == second_profile.agency_id

    def test_assigned_agent_can_reassign_to_colleague(self, auth_agent, agent_user, second_agent, owner_user):
        _join_agency(agent_user, second_agent)
        relation = self._make_relation(agent_user, owner_user)
        second_profile = AgentProfile.objects.get(user=second_agent)

        response = auth_agent.post(f'/api/v1/agencies/mandates/{relation.id}/reassign/', {
            'agent_profile_id': str(second_profile.id),
        })
        assert response.status_code == status.HTTP_200_OK

    def test_outsider_cannot_reassign(self, auth_agent2, agent_user, second_agent, owner_user):
        # second_agent n'a pas rejoint l'agence de agent_user
        relation = self._make_relation(agent_user, owner_user)
        response = auth_agent2.post(f'/api/v1/agencies/mandates/{relation.id}/reassign/', {
            'agent_profile_id': str(AgentProfile.objects.get(user=second_agent).id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_reassign_to_agent_outside_agency(self, auth_agent, agent_user, second_agent, owner_user):
        # second_agent garde sa propre agence solo
        relation = self._make_relation(agent_user, owner_user)
        second_profile = AgentProfile.objects.get(user=second_agent)

        response = auth_agent.post(f'/api/v1/agencies/mandates/{relation.id}/reassign/', {
            'agent_profile_id': str(second_profile.id),
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_reassign_to_same_agent(self, auth_agent, agent_user, owner_user):
        relation = self._make_relation(agent_user, owner_user)
        profile = AgentProfile.objects.get(user=agent_user)

        response = auth_agent.post(f'/api/v1/agencies/mandates/{relation.id}/reassign/', {
            'agent_profile_id': str(profile.id),
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
