import pytest
from rest_framework import status
from apps.agents.models import AgentProfile
from apps.agents.services import ensure_agent_profile_and_agency
from apps.agencies.services import transfer_agent_to_agency
from apps.disputes.models import Dispute
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def _make_agent(create_user, email, phone):
    user = create_user(email=email, phone=phone, role='agent', is_validated=True)
    ensure_agent_profile_and_agency(user)
    return user


class TestAgencyReliabilityScore:

    def test_aggregates_across_all_members(self, agent_user, create_user, client_user):
        colleague = _make_agent(create_user, 'colleague_rep@test.com', '+237670000300')
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        colleague_profile = AgentProfile.objects.get(user=colleague)
        transfer_agent_to_agency(colleague_profile, gerant_profile.agency)

        Review.objects.create(reviewer=client_user, agent=agent_user, agent_rating=5)
        Review.objects.create(reviewer=client_user, agent=colleague, agent_rating=3)

        gerant_profile.agency.update_reliability_score()
        gerant_profile.agency.refresh_from_db()

        assert gerant_profile.agency.total_reviews == 2
        assert gerant_profile.agency.reliability_score == 4.0  # (5+3)/2, pas moyenne des moyennes

    def test_solo_agency_matches_agent_score(self, agent_user, client_user):
        Review.objects.create(reviewer=client_user, agent=agent_user, agent_rating=4)
        profile = AgentProfile.objects.get(user=agent_user)
        profile.update_reliability_score()
        profile.refresh_from_db()

        assert profile.reliability_score == 4.0
        assert profile.agency.reliability_score == 4.0
        assert profile.agency.total_reviews == 1

    def test_no_reviews_gives_zero(self, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        profile.agency.update_reliability_score()
        profile.agency.refresh_from_db()
        assert profile.agency.reliability_score == 0.0
        assert profile.agency.total_reviews == 0

    def test_recomputed_when_agent_leaves(self, agent_user, create_user, client_user):
        colleague = _make_agent(create_user, 'leaver_rep@test.com', '+237670000301')
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        colleague_profile = AgentProfile.objects.get(user=colleague)
        old_solo_agency = colleague_profile.agency
        transfer_agent_to_agency(colleague_profile, gerant_profile.agency)

        Review.objects.create(reviewer=client_user, agent=colleague, agent_rating=2)
        colleague_profile.update_reliability_score()
        gerant_profile.agency.refresh_from_db()
        assert gerant_profile.agency.total_reviews == 1

        # Le colleague repart -- l'agence du gerant ne doit plus compter son avis
        transfer_agent_to_agency(colleague_profile, old_solo_agency)
        gerant_profile.agency.refresh_from_db()
        assert gerant_profile.agency.total_reviews == 0


class TestDisputesConfirmedAgainst:

    def test_claimant_wins_increments_counter(self, auth_admin, client_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='reviewing',
            agency=profile.agency,
        )
        auth_admin.post(f'/api/v1/admin-panel/disputes/{dispute.id}/decide/', {
            'decision': 'claimant_wins', 'decision_note': 'Confirme',
        })
        profile.agency.refresh_from_db()
        assert profile.agency.disputes_confirmed_against == 1

    def test_defendant_wins_does_not_increment(self, auth_admin, client_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='reviewing',
            agency=profile.agency,
        )
        auth_admin.post(f'/api/v1/admin-panel/disputes/{dispute.id}/decide/', {
            'decision': 'defendant_wins', 'decision_note': 'Rejete',
        })
        profile.agency.refresh_from_db()
        assert profile.agency.disputes_confirmed_against == 0

    def test_no_agency_no_crash(self, auth_admin, client_user, owner_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=owner_user, dispute_type='other',
            title='T', description='Description suffisamment longue', status='reviewing',
        )
        r = auth_admin.post(f'/api/v1/admin-panel/disputes/{dispute.id}/decide/', {
            'decision': 'claimant_wins', 'decision_note': 'Confirme',
        })
        assert r.status_code == status.HTTP_200_OK


class TestSerializerExposure:

    def test_agency_serializer_exposes_reputation(self, auth_agent, agent_user):
        r = auth_agent.get('/api/v1/agencies/me/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data['data']
        assert 'reliability_score' in data
        assert 'total_reviews' in data
        assert 'disputes_confirmed_against' in data

    def test_public_agent_serializer_exposes_agency_reputation(self, api_client, agent_user, client_user):
        Review.objects.create(reviewer=client_user, agent=agent_user, agent_rating=5)
        profile = AgentProfile.objects.get(user=agent_user)
        profile.update_reliability_score()

        r = api_client.get(f'/api/v1/agents/{profile.id}/')
        assert r.status_code == status.HTTP_200_OK
        agency_data = r.data['data']['agency']
        assert agency_data['reliability_score'] == 5.0
        assert agency_data['total_reviews'] == 1
