import datetime
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.agents.models import AgentProfile, OwnerAgentRelation
from apps.agencies.models import AgencyInvitation
from apps.agencies.tasks import expire_stale_invitations
from apps.contracts.models import AgentOwnerContract
from apps.visits.models import VisitRequest
from apps.visits.tasks import send_visit_reminders

pytestmark = pytest.mark.django_db


def _auth_as(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestAgentOwnerContract:

    def _active_mandate(self, agent_user, owner_user):
        profile = AgentProfile.objects.get(user=agent_user)
        OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency, status='active',
            contract_start=datetime.date.today(),
        )
        return profile.agency

    def test_agent_can_create_contract_with_active_mandate(self, auth_agent, agent_user, owner_user):
        self._active_mandate(agent_user, owner_user)
        r = auth_agent.post('/api/v1/contracts/agent-owner/create/', {
            'owner': str(owner_user.id), 'commission_percent': 12,
            'start_date': str(datetime.date.today()),
            'terms': "Gestion complete du bien, visites et encaissement des loyers.",
        })
        assert r.status_code == status.HTTP_201_CREATED
        contract = AgentOwnerContract.objects.get(agent=agent_user, owner=owner_user)
        assert contract.agency_id == AgentProfile.objects.get(user=agent_user).agency_id

    def test_agent_without_mandate_cannot_create_contract(self, auth_agent, owner_user):
        r = auth_agent.post('/api/v1/contracts/agent-owner/create/', {
            'owner': str(owner_user.id), 'commission_percent': 12,
            'start_date': str(datetime.date.today()),
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_both_parties_sign(self, auth_agent, agent_user, owner_user):
        self._active_mandate(agent_user, owner_user)
        contract = AgentOwnerContract.objects.create(
            agent=agent_user, owner=owner_user, agency=AgentProfile.objects.get(user=agent_user).agency,
            commission_percent=10, start_date=datetime.date.today(),
        )
        r1 = auth_agent.post(f'/api/v1/contracts/agent-owner/{contract.id}/sign/')
        assert r1.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.signed_by_agent is True
        assert contract.signed_at is None

        r2 = _auth_as(owner_user).post(f'/api/v1/contracts/agent-owner/{contract.id}/sign/')
        assert r2.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.is_fully_signed()
        assert contract.signed_at is not None

    def test_unrelated_user_cannot_sign(self, agent_user, owner_user, create_user):
        contract = AgentOwnerContract.objects.create(
            agent=agent_user, owner=owner_user,
            commission_percent=10, start_date=datetime.date.today(),
        )
        stranger = create_user(email='contract_stranger@test.com', phone='+237670000700', role='owner')
        r = _auth_as(stranger).post(f'/api/v1/contracts/agent-owner/{contract.id}/sign/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_pdf_download(self, agent_user, owner_user):
        self._active_mandate(agent_user, owner_user)
        contract = AgentOwnerContract.objects.create(
            agent=agent_user, owner=owner_user, agency=AgentProfile.objects.get(user=agent_user).agency,
            commission_percent=10, start_date=datetime.date.today(),
        )
        r = _auth_as(owner_user).get(f'/api/v1/contracts/agent-owner/{contract.id}/pdf/')
        assert r.status_code == status.HTTP_200_OK
        assert r.content.startswith(b'%PDF')

    def test_my_contracts_list(self, auth_agent, agent_user, owner_user):
        self._active_mandate(agent_user, owner_user)
        AgentOwnerContract.objects.create(
            agent=agent_user, owner=owner_user, agency=AgentProfile.objects.get(user=agent_user).agency,
            commission_percent=10, start_date=datetime.date.today(),
        )
        r = auth_agent.get('/api/v1/contracts/agent-owner/')
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data['data']) == 1


class TestAgencyInvitationExpiry:

    def test_stale_invitation_expires_and_notifies_both(self, agent_user, create_user):
        from apps.notifications.models import Notification
        invited = create_user(email='invitee_expiry@test.com', phone='+237670000701', role='agent', is_validated=True)
        agency = AgentProfile.objects.get(user=agent_user).agency
        invitation = AgencyInvitation.objects.create(
            agency=agency, invited_user=invited, invited_by=agent_user, status='pending',
        )
        AgencyInvitation.objects.filter(id=invitation.id).update(
            created_at=timezone.now() - datetime.timedelta(days=8)
        )

        expire_stale_invitations()

        invitation.refresh_from_db()
        assert invitation.status == 'expired'
        assert Notification.objects.filter(recipient=invited, notification_type='agency_invitation').exists()
        assert Notification.objects.filter(recipient=agent_user, notification_type='agency_invitation').exists()

    def test_fresh_invitation_not_expired(self, agent_user, create_user):
        invited = create_user(email='invitee_fresh@test.com', phone='+237670000702', role='agent', is_validated=True)
        agency = AgentProfile.objects.get(user=agent_user).agency
        invitation = AgencyInvitation.objects.create(
            agency=agency, invited_user=invited, invited_by=agent_user, status='pending',
        )
        expire_stale_invitations()
        invitation.refresh_from_db()
        assert invitation.status == 'pending'


class TestVisitReminders:

    def test_reminder_sent_for_tomorrow_visit(self, agent_user, client_user, property_obj):
        visit = VisitRequest.objects.create(
            client=client_user, agent=agent_user, visit_property=property_obj,
            status='confirmed', scheduled_date=timezone.now().date() + datetime.timedelta(days=1),
        )
        send_visit_reminders()

        from apps.notifications.models import Notification
        assert Notification.objects.filter(recipient=client_user, notification_type='visit_scheduled').exists()
        assert Notification.objects.filter(recipient=agent_user, notification_type='visit_scheduled').exists()
        visit.refresh_from_db()
        assert visit.reminder_sent is True

    def test_reminder_not_sent_twice(self, agent_user, client_user, property_obj):
        from apps.notifications.models import Notification
        visit = VisitRequest.objects.create(
            client=client_user, agent=agent_user, visit_property=property_obj,
            status='confirmed', scheduled_date=timezone.now().date() + datetime.timedelta(days=1),
        )
        send_visit_reminders()
        count_first = Notification.objects.filter(recipient=client_user).count()
        send_visit_reminders()
        count_second = Notification.objects.filter(recipient=client_user).count()
        assert count_first == count_second

    def test_no_reminder_for_visit_in_two_days(self, agent_user, client_user, property_obj):
        VisitRequest.objects.create(
            client=client_user, agent=agent_user, visit_property=property_obj,
            status='confirmed', scheduled_date=timezone.now().date() + datetime.timedelta(days=2),
        )
        send_visit_reminders()
        from apps.notifications.models import Notification
        assert not Notification.objects.filter(recipient=client_user, notification_type='visit_scheduled').exists()

    def test_no_reminder_for_pending_visit(self, agent_user, client_user, property_obj):
        VisitRequest.objects.create(
            client=client_user, agent=agent_user, visit_property=property_obj,
            status='pending', scheduled_date=timezone.now().date() + datetime.timedelta(days=1),
        )
        send_visit_reminders()
        from apps.notifications.models import Notification
        assert not Notification.objects.filter(recipient=client_user, notification_type='visit_scheduled').exists()
