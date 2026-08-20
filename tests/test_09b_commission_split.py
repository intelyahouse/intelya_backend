import datetime
from unittest.mock import patch
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile
from apps.agencies.services import transfer_agent_to_agency
from apps.contracts.models import LeaseContract
from apps.payments.models import Transaction, PaymentSplitEntry
from apps.payments.services.disbursement import process_rent_transfer, _agency_commission_plan
from apps.network.models import Collaboration

pytestmark = pytest.mark.django_db

MOCK_OK = {'success': True, 'reference': 'KPAY-OK'}
MOCK_FAIL = {'success': False, 'error': 'Fonds insuffisants'}


@pytest.fixture
def second_agent(create_user):
    return create_user(
        email="agent2@test.com", phone="+237670000120",
        role="agent", is_validated=True,
    )


@pytest.fixture
def auth_agent2(second_agent):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=second_agent)
    return client


def _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=0):
    profile = AgentProfile.objects.get(user=agent_user)
    return LeaseContract.objects.create(
        tenant=client_with_agent, owner=owner_user, agent=agent_user,
        agency=profile.agency, rental_property=property_obj,
        monthly_rent=150000, deposit_amount=300000,
        agent_commission=agent_commission,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=365),
        payment_day=5, status='active',
        signed_by_tenant=True, signed_by_owner=True,
    )


def _rent_txn(lease, amount=150000, net_amount=147000):
    return Transaction.objects.create(
        reference=f"IH-RENT-{lease.id}", transaction_type='rent',
        amount=amount, platform_fee=amount - net_amount, net_amount=net_amount,
        status='completed', payment_method='mtn',
        related_lease_id=lease.id,
    )


class TestCommissionPlan:

    def test_no_agency_no_commission(self, owner_user, client_with_agent, property_obj, agent_user):
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=0)
        collab, plan = _agency_commission_plan(lease)
        assert collab is None
        assert plan == []

    def test_simple_agent_commission(self, owner_user, client_with_agent, property_obj, agent_user):
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=10000)
        collab, plan = _agency_commission_plan(lease)
        assert collab is None
        assert len(plan) == 1
        assert plan[0][0].id == lease.agency_id
        assert plan[0][1] == 10000

    def test_accepted_collaboration_takes_priority(
        self, owner_user, client_with_agent, property_obj, agent_user, second_agent
    ):
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=10000)
        second_profile = AgentProfile.objects.get(user=second_agent)
        agent_profile = AgentProfile.objects.get(user=agent_user)
        collaboration = Collaboration.objects.create(
            property=property_obj, client_agency=second_profile.agency,
            property_agency=agent_profile.agency, initiated_by=second_agent,
            client_agency_amount=100, property_agency_amount=100, total_amount=200,
            status='accepted', last_proposed_by_agency=second_profile.agency,
        )
        collab, plan = _agency_commission_plan(lease)
        assert collab.id == collaboration.id
        assert len(plan) == 2
        amounts = {str(a.id): amt for a, amt in plan}
        assert amounts[str(second_profile.agency_id)] == 100
        assert amounts[str(agent_profile.agency_id)] == 100


class TestProcessRentTransfer:

    def test_simple_commission_disbursed_and_marked_paid(
        self, owner_user, client_with_agent, property_obj, agent_user
    ):
        agency = AgentProfile.objects.get(user=agent_user).agency
        agency.mtn_momo_number = '+237670000001'
        agency.save(update_fields=['mtn_momo_number'])

        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=10000)
        txn = _rent_txn(lease)

        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK) as mock_disburse:
            process_rent_transfer(txn)

        assert mock_disburse.called
        lease.refresh_from_db()
        assert lease.commission_paid is True

        entries = PaymentSplitEntry.objects.filter(transaction=txn)
        assert entries.count() == 1
        assert entries.first().status == 'completed'
        assert entries.first().agency_id == agency.id

    def test_no_double_disbursement_on_replay(
        self, owner_user, client_with_agent, property_obj, agent_user
    ):
        agency = AgentProfile.objects.get(user=agent_user).agency
        agency.mtn_momo_number = '+237670000001'
        agency.save(update_fields=['mtn_momo_number'])
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=10000)
        txn = _rent_txn(lease)

        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK) as mock_disburse:
            process_rent_transfer(txn)
            process_rent_transfer(txn)

        assert mock_disburse.call_count == 1
        assert PaymentSplitEntry.objects.filter(transaction=txn).count() == 1

    def test_missing_phone_marks_entry_failed_without_crash(
        self, owner_user, client_with_agent, property_obj, agent_user
    ):
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=10000)
        txn = _rent_txn(lease)

        process_rent_transfer(txn)

        entry = PaymentSplitEntry.objects.get(transaction=txn)
        assert entry.status == 'failed'
        assert 'mobile money' in entry.error_message.lower()

    def test_collaboration_split_disbursed_to_both_agencies(
        self, owner_user, client_with_agent, property_obj, agent_user, second_agent
    ):
        agent_profile = AgentProfile.objects.get(user=agent_user)
        second_profile = AgentProfile.objects.get(user=second_agent)
        agent_profile.agency.mtn_momo_number = '+237670000001'
        agent_profile.agency.save(update_fields=['mtn_momo_number'])
        second_profile.agency.mtn_momo_number = '+237670000002'
        second_profile.agency.save(update_fields=['mtn_momo_number'])

        collaboration = Collaboration.objects.create(
            property=property_obj, client_agency=second_profile.agency,
            property_agency=agent_profile.agency, initiated_by=second_agent,
            client_agency_amount=100, property_agency_amount=100, total_amount=200,
            status='accepted', last_proposed_by_agency=second_profile.agency,
        )
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, agent_commission=10000)
        txn = _rent_txn(lease)

        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK):
            process_rent_transfer(txn)

        collaboration.refresh_from_db()
        assert collaboration.commission_disbursed is True
        assert PaymentSplitEntry.objects.filter(transaction=txn).count() == 2
        # la commission simple du bail (agent_commission) n'est PAS aussi versee
        lease.refresh_from_db()
        assert lease.commission_paid is False

    def test_no_related_lease_is_noop(self):
        txn = Transaction.objects.create(
            reference='IH-NOLEASE', transaction_type='rent',
            amount=1000, net_amount=1000, status='completed',
        )
        process_rent_transfer(txn)  # ne doit pas planter
        assert PaymentSplitEntry.objects.count() == 0

    def test_non_rent_transaction_is_noop(self, client_user):
        txn = Transaction.objects.create(
            reference='IH-VISIT', transaction_type='visit_fee',
            amount=1000, net_amount=1000, status='completed',
            payer=client_user,
        )
        process_rent_transfer(txn)
        assert PaymentSplitEntry.objects.count() == 0


class TestAgencyPaymentInfoEndpoint:

    def test_gerant_can_set_payment_info(self, auth_agent, agent_user):
        response = auth_agent.patch('/api/v1/agencies/me/', {
            'mtn_momo_number': '+237670000099',
        })
        assert response.status_code == status.HTTP_200_OK
        agency = AgentProfile.objects.get(user=agent_user).agency
        agency.refresh_from_db()
        assert agency.mtn_momo_number == '+237670000099'

    def test_non_gerant_cannot_set_payment_info(self, auth_agent2, agent_user, second_agent):
        second_profile = AgentProfile.objects.get(user=second_agent)
        agent_profile = AgentProfile.objects.get(user=agent_user)
        transfer_agent_to_agency(second_profile, agent_profile.agency)
        second_agent.refresh_from_db()
        auth_agent2.force_authenticate(user=second_agent)

        response = auth_agent2.patch('/api/v1/agencies/me/', {
            'mtn_momo_number': '+237670000098',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
