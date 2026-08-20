import datetime
import pytest
from django.utils import timezone
from rest_framework import status
from apps.agents.models import AgentProfile
from apps.disputes.models import Dispute
from apps.notifications.models import Notification
from apps.disputes.tasks import escalate_stale_disputes

pytestmark = pytest.mark.django_db


class TestDisputeAgencyDerivation:

    def test_dispute_against_agent_gets_agency(self, auth_client, client_user, agent_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id), 'dispute_type': 'agent',
            'title': 'Agent injoignable', 'description': "N'a pas repondu depuis 3 jours",
        })
        assert r.status_code == status.HTTP_201_CREATED
        dispute = Dispute.objects.get(claimant=client_user, defendant=agent_user)
        assert dispute.agency_id == AgentProfile.objects.get(user=agent_user).agency_id

    def test_dispute_against_non_agent_has_no_agency(self, auth_client, client_user, owner_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(owner_user.id), 'dispute_type': 'other',
            'title': 'Litige proprietaire', 'description': "Description suffisamment longue",
        })
        assert r.status_code == status.HTTP_201_CREATED
        dispute = Dispute.objects.get(claimant=client_user, defendant=owner_user)
        assert dispute.agency_id is None


class TestDisputeNotifications:

    def test_defendant_and_admins_notified_on_creation(self, auth_client, client_user, agent_user, admin_user):
        auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id), 'dispute_type': 'agent',
            'title': 'Test notif', 'description': 'Description suffisamment longue',
        })
        assert Notification.objects.filter(recipient=agent_user, notification_type='dispute_opened').exists()
        assert Notification.objects.filter(recipient=admin_user, notification_type='dispute_opened').exists()

    def test_claimant_and_admins_notified_on_response(self, client_user, agent_user, admin_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='open',
        )
        from rest_framework.test import APIClient
        auth_agent = APIClient()
        auth_agent.force_authenticate(user=agent_user)
        auth_agent.post(f'/api/v1/disputes/disputes/{dispute.id}/respond/', {'response': 'Je conteste'})
        assert Notification.objects.filter(recipient=client_user, notification_type='dispute_responded').exists()
        assert Notification.objects.filter(recipient=admin_user, notification_type='dispute_responded').exists()

    def test_both_parties_notified_on_admin_decision(self, auth_admin, client_user, agent_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='reviewing',
        )
        auth_admin.post(f'/api/v1/admin-panel/disputes/{dispute.id}/decide/', {
            'decision': 'claimant_wins', 'decision_note': 'Preuves confirmees',
        })
        assert Notification.objects.filter(recipient=client_user, notification_type='dispute_decided').exists()
        assert Notification.objects.filter(recipient=agent_user, notification_type='dispute_decided').exists()


class TestGerantVisibility:

    def test_gerant_sees_dispute_against_agency_member(self, agent_user, create_user, client_user):
        from apps.agents.services import ensure_agent_profile_and_agency
        member = create_user(email='member_dispute@test.com', phone='+237670000210', role='agent', is_validated=True)
        ensure_agent_profile_and_agency(member)
        member_profile = AgentProfile.objects.get(user=member)
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        member_profile.agency = gerant_profile.agency
        member_profile.save(update_fields=['agency'])

        dispute = Dispute.objects.create(
            claimant=client_user, defendant=member, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='open',
            agency=gerant_profile.agency,
        )

        from rest_framework.test import APIClient
        auth_gerant = APIClient()
        auth_gerant.force_authenticate(user=agent_user)
        r = auth_gerant.get('/api/v1/disputes/disputes/')
        ids = [d['id'] for d in r.data['results']]
        assert str(dispute.id) in ids

    def test_regular_member_does_not_see_colleagues_disputes(self, agent_user, create_user, client_user):
        from apps.agents.services import ensure_agent_profile_and_agency
        member = create_user(email='member2_dispute@test.com', phone='+237670000211', role='agent', is_validated=True)
        ensure_agent_profile_and_agency(member)
        member_profile = AgentProfile.objects.get(user=member)
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        member_profile.agency = gerant_profile.agency
        member_profile.save(update_fields=['agency'])

        other_member = create_user(email='member3_dispute@test.com', phone='+237670000212', role='agent', is_validated=True)
        ensure_agent_profile_and_agency(other_member)
        other_profile = AgentProfile.objects.get(user=other_member)
        other_profile.agency = gerant_profile.agency
        other_profile.save(update_fields=['agency'])

        dispute = Dispute.objects.create(
            claimant=client_user, defendant=other_member, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='open',
            agency=gerant_profile.agency,
        )

        from rest_framework.test import APIClient
        auth_member = APIClient()
        auth_member.force_authenticate(user=member)
        r = auth_member.get('/api/v1/disputes/disputes/')
        ids = [d['id'] for d in r.data['results']]
        assert str(dispute.id) not in ids


class TestEscalation:

    def test_stale_open_dispute_escalated(self, client_user, agent_user, admin_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='open',
        )
        Dispute.objects.filter(id=dispute.id).update(
            created_at=timezone.now() - datetime.timedelta(hours=49)
        )

        escalate_stale_disputes()

        dispute.refresh_from_db()
        assert dispute.status == 'reviewing'
        assert Notification.objects.filter(recipient=admin_user, notification_type='dispute_opened').exists()

    def test_fresh_open_dispute_not_escalated(self, client_user, agent_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user, dispute_type='agent',
            title='T', description='Description suffisamment longue', status='open',
        )
        escalate_stale_disputes()
        dispute.refresh_from_db()
        assert dispute.status == 'open'
