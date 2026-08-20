import datetime
from decimal import Decimal
from unittest.mock import patch
import pytest
from rest_framework import status
from apps.agents.models import AgentProfile
from apps.contracts.models import LeaseContract
from apps.payments.models import Transaction, PaymentSplitEntry, RentFeeTier
from apps.payments.services.fees import get_rent_fee, split_rent_fee
from apps.payments.services.disbursement import process_rent_transfer

pytestmark = pytest.mark.django_db

MOCK_OK = {'success': True, 'reference': 'KPAY-OK'}


def _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000):
    profile = AgentProfile.objects.get(user=agent_user)
    return LeaseContract.objects.create(
        tenant=client_with_agent, owner=owner_user, agent=agent_user,
        agency=profile.agency, rental_property=property_obj,
        monthly_rent=monthly_rent, deposit_amount=monthly_rent * 2,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=365),
        payment_day=5, status='active',
        signed_by_tenant=True, signed_by_owner=True,
    )


def _rent_txn(lease, monthly_rent, agency_fee_amount, platform_fee=0):
    total = monthly_rent + platform_fee + agency_fee_amount
    return Transaction.objects.create(
        reference=f"IH-RENT-{lease.id}", transaction_type='rent',
        amount=total, platform_fee=platform_fee, net_amount=monthly_rent,
        agency_fee_amount=agency_fee_amount,
        status='completed', payment_method='mtn',
        related_lease_id=lease.id,
    )


class TestRentFeeTiers:

    def test_tier_1_applies(self, settings):
        settings.RENT_SURCHARGE_ENABLED = True
        assert get_rent_fee(Decimal('30000')) == Decimal('500')

    def test_tier_2_applies(self, settings):
        settings.RENT_SURCHARGE_ENABLED = True
        assert get_rent_fee(Decimal('75000')) == Decimal('1000')

    def test_boundary_50000_is_tier_1(self, settings):
        settings.RENT_SURCHARGE_ENABLED = True
        assert get_rent_fee(Decimal('50000')) == Decimal('500')

    def test_boundary_50001_is_tier_2(self, settings):
        settings.RENT_SURCHARGE_ENABLED = True
        assert get_rent_fee(Decimal('50001')) == Decimal('1000')

    def test_above_all_tiers_no_fee(self, settings):
        settings.RENT_SURCHARGE_ENABLED = True
        assert get_rent_fee(Decimal('500000')) == Decimal('0')

    def test_disabled_by_free_mode(self, settings):
        settings.RENT_SURCHARGE_ENABLED = False
        assert get_rent_fee(Decimal('30000')) == Decimal('0')

    def test_split_60_40(self, settings):
        settings.RENT_SURCHARGE_PLATFORM_PERCENT = 60
        platform_share, agency_share = split_rent_fee(Decimal('500'))
        assert platform_share == Decimal('300.00')
        assert agency_share == Decimal('200.00')


class TestInitiatePaymentRent:

    def test_server_computes_rent_plus_fee_ignoring_client_amount(
        self, settings, auth_client_with_agent, client_with_agent, agent_user, owner_user, property_obj
    ):
        settings.RENT_SURCHARGE_ENABLED = True
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)

        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            response = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '30000',  # doit etre ignore pour un loyer, mais doit etre realiste
                'payment_method': 'mtn', 'phone_number': '+237670000001',
                'related_type': 'rent', 'related_id': str(lease.id),
            })
        assert response.status_code == status.HTTP_201_CREATED
        breakdown = response.data['data']['breakdown']
        assert breakdown['rent_total'] == 30000
        assert breakdown['fee'] == 500
        assert breakdown['platform_share'] == 300
        assert breakdown['agency_share'] == 200
        assert breakdown['total'] == 30500

        txn = Transaction.objects.get(related_lease_id=lease.id)
        assert float(txn.amount) == 30500
        assert float(txn.net_amount) == 30000
        assert float(txn.agency_fee_amount) == 200

    def test_owner_never_loses_a_share_of_rent(
        self, settings, auth_client_with_agent, client_with_agent, agent_user, owner_user, property_obj
    ):
        settings.RENT_SURCHARGE_ENABLED = True
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)

        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '30000', 'payment_method': 'mtn', 'phone_number': '+237670000001',
                'related_type': 'rent', 'related_id': str(lease.id),
            })
        txn = Transaction.objects.get(related_lease_id=lease.id)
        assert float(txn.net_amount) == float(lease.monthly_rent)

    def test_multi_month_payment(
        self, settings, auth_client_with_agent, client_with_agent, agent_user, owner_user, property_obj
    ):
        settings.RENT_SURCHARGE_ENABLED = True
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)

        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            response = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '30000', 'payment_method': 'mtn', 'phone_number': '+237670000001',
                'related_type': 'rent', 'related_id': str(lease.id), 'months': 3,
            })
        breakdown = response.data['data']['breakdown']
        assert breakdown['rent_total'] == 90000
        assert breakdown['fee'] == 1500
        assert breakdown['total'] == 91500

    def test_no_fee_when_free_mode(
        self, settings, auth_client_with_agent, client_with_agent, agent_user, owner_user, property_obj
    ):
        settings.RENT_SURCHARGE_ENABLED = False
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)

        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=MOCK_OK):
            response = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '30000', 'payment_method': 'mtn', 'phone_number': '+237670000001',
                'related_type': 'rent', 'related_id': str(lease.id),
            })
        breakdown = response.data['data']['breakdown']
        assert breakdown['fee'] == 0
        assert breakdown['total'] == 30000

    def test_other_tenant_cannot_pay_this_lease(
        self, settings, auth_client, client_with_agent, agent_user, owner_user, property_obj, create_user
    ):
        settings.RENT_SURCHARGE_ENABLED = True
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)
        other = create_user(email='other_tenant@test.com', phone='+237670000199', role='client')
        from rest_framework.test import APIClient
        auth_other = APIClient()
        auth_other.force_authenticate(user=other)

        response = auth_other.post('/api/v1/payments/initiate/', {
            'amount': '30000', 'payment_method': 'mtn',
            'related_type': 'rent', 'related_id': str(lease.id),
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestProcessRentTransferDisbursement:

    def test_agency_receives_its_share(self, owner_user, client_with_agent, property_obj, agent_user):
        owner_user.owner_profile.mtn_momo_number = '+237670000003'
        owner_user.owner_profile.save(update_fields=['mtn_momo_number'])
        agency = AgentProfile.objects.get(user=agent_user).agency
        agency.mtn_momo_number = '+237670000001'
        agency.save(update_fields=['mtn_momo_number'])
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)
        txn = _rent_txn(lease, monthly_rent=30000, agency_fee_amount=200, platform_fee=300)

        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK) as mock_disburse:
            process_rent_transfer(txn)

        assert mock_disburse.call_count == 2  # proprietaire + agence
        entry = PaymentSplitEntry.objects.get(transaction=txn)
        assert entry.status == 'completed'
        assert entry.agency_id == agency.id
        assert float(entry.amount) == 200

    def test_no_double_disbursement_on_replay(self, owner_user, client_with_agent, property_obj, agent_user):
        agency = AgentProfile.objects.get(user=agent_user).agency
        agency.mtn_momo_number = '+237670000001'
        agency.save(update_fields=['mtn_momo_number'])
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)
        txn = _rent_txn(lease, monthly_rent=30000, agency_fee_amount=200, platform_fee=300)

        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK) as mock_disburse:
            process_rent_transfer(txn)
            process_rent_transfer(txn)

        assert PaymentSplitEntry.objects.filter(transaction=txn).count() == 1

    def test_recurring_across_two_months(self, owner_user, client_with_agent, property_obj, agent_user):
        agency = AgentProfile.objects.get(user=agent_user).agency
        agency.mtn_momo_number = '+237670000001'
        agency.save(update_fields=['mtn_momo_number'])
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)
        txn1 = _rent_txn(lease, monthly_rent=30000, agency_fee_amount=200, platform_fee=300)

        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK):
            process_rent_transfer(txn1)

        txn2 = Transaction.objects.create(
            reference=f"IH-RENT2-{lease.id}", transaction_type='rent',
            amount=30500, platform_fee=300, net_amount=30000, agency_fee_amount=200,
            status='completed', payment_method='mtn', related_lease_id=lease.id,
        )
        with patch('apps.payments.services.kpay.kpay_service.disburse', return_value=MOCK_OK) as mock_disburse:
            process_rent_transfer(txn2)

        assert mock_disburse.called  # le mois suivant declenche a nouveau un versement
        assert PaymentSplitEntry.objects.filter(transaction=txn2).count() == 1

    def test_missing_agency_phone_marks_failed(self, owner_user, client_with_agent, property_obj, agent_user):
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)
        txn = _rent_txn(lease, monthly_rent=30000, agency_fee_amount=200, platform_fee=300)

        process_rent_transfer(txn)

        entry = PaymentSplitEntry.objects.get(transaction=txn)
        assert entry.status == 'failed'

    def test_no_agency_fee_no_entry_created(self, owner_user, client_with_agent, property_obj, agent_user):
        lease = _lease(agent_user, owner_user, client_with_agent, property_obj, monthly_rent=30000)
        txn = _rent_txn(lease, monthly_rent=30000, agency_fee_amount=0, platform_fee=0)

        process_rent_transfer(txn)

        assert PaymentSplitEntry.objects.filter(transaction=txn).count() == 0
