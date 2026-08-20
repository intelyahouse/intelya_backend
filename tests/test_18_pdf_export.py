import datetime
import pytest
from django.utils import timezone
from rest_framework import status
from apps.agents.models import AgentProfile, OwnerAgentRelation
from apps.contracts.models import LeaseContract
from apps.leases.models import RentPayment
from apps.payments.models import Transaction

pytestmark = pytest.mark.django_db


def _paid_payment(agent_user, owner_user, client_with_agent, property_obj):
    profile = AgentProfile.objects.get(user=agent_user)
    lease = LeaseContract.objects.create(
        tenant=client_with_agent, owner=owner_user, agent=agent_user, agency=profile.agency,
        rental_property=property_obj, monthly_rent=30000, deposit_amount=60000,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=365),
        payment_day=5, status='active', signed_by_tenant=True, signed_by_owner=True,
    )
    return RentPayment.objects.create(
        lease=lease, tenant=client_with_agent, amount=30000,
        platform_fee=300, agency_fee_amount=200,
        due_date=datetime.date.today(), paid_at=timezone.now(),
        status='paid', payment_method='mtn', payment_reference='IH-REC-001',
        period_month=datetime.date.today().month, period_year=datetime.date.today().year,
    )


class TestRentReceiptPDF:

    def test_tenant_can_download(self, auth_client_with_agent, agent_user, owner_user, client_with_agent, property_obj):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        r = auth_client_with_agent.get(f'/api/v1/leases/payments/{payment.id}/receipt/')
        assert r.status_code == status.HTTP_200_OK
        assert r['Content-Type'] == 'application/pdf'
        assert r.content.startswith(b'%PDF')

    def test_owner_can_download(self, owner_user, agent_user, client_with_agent, property_obj):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        from rest_framework.test import APIClient
        auth_owner = APIClient()
        auth_owner.force_authenticate(user=owner_user)
        r = auth_owner.get(f'/api/v1/leases/payments/{payment.id}/receipt/')
        assert r.status_code == status.HTTP_200_OK

    def test_agency_colleague_can_download(self, agent_user, owner_user, client_with_agent, property_obj, create_user):
        from apps.agents.services import ensure_agent_profile_and_agency
        from apps.agencies.services import transfer_agent_to_agency
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)

        colleague = create_user(email='pdf_colleague@test.com', phone='+237670000600', role='agent', is_validated=True)
        ensure_agent_profile_and_agency(colleague)
        colleague_profile = AgentProfile.objects.get(user=colleague)
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        transfer_agent_to_agency(colleague_profile, gerant_profile.agency)

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        fresh_colleague = get_user_model().objects.get(pk=colleague.pk)
        auth_colleague = APIClient()
        auth_colleague.force_authenticate(user=fresh_colleague)

        r = auth_colleague.get(f'/api/v1/leases/payments/{payment.id}/receipt/')
        assert r.status_code == status.HTTP_200_OK

    def test_unrelated_user_blocked(self, agent_user, owner_user, client_with_agent, property_obj, create_user):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        stranger = create_user(email='pdf_stranger@test.com', phone='+237670000601', role='client')
        from rest_framework.test import APIClient
        auth_stranger = APIClient()
        auth_stranger.force_authenticate(user=stranger)
        r = auth_stranger.get(f'/api/v1/leases/payments/{payment.id}/receipt/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_unpaid_payment_not_found(self, agent_user, owner_user, client_with_agent, property_obj):
        profile = AgentProfile.objects.get(user=agent_user)
        lease = LeaseContract.objects.create(
            tenant=client_with_agent, owner=owner_user, agent=agent_user, agency=profile.agency,
            rental_property=property_obj, monthly_rent=30000, deposit_amount=60000,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=365),
            payment_day=5, status='active', signed_by_tenant=True, signed_by_owner=True,
        )
        payment = RentPayment.objects.create(
            lease=lease, tenant=client_with_agent, amount=30000, status='pending',
            due_date=datetime.date.today(),
            period_month=datetime.date.today().month, period_year=datetime.date.today().year,
        )
        from rest_framework.test import APIClient
        auth_owner = APIClient()
        auth_owner.force_authenticate(user=owner_user)
        r = auth_owner.get(f'/api/v1/leases/payments/{payment.id}/receipt/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_blocked(self, api_client, agent_user, owner_user, client_with_agent, property_obj):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        r = api_client.get(f'/api/v1/leases/payments/{payment.id}/receipt/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestMandatePDF:

    def test_owner_can_download(self, owner_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        relation = OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency, status='active',
            contract_start=datetime.date.today(),
        )
        from rest_framework.test import APIClient
        auth_owner = APIClient()
        auth_owner.force_authenticate(user=owner_user)
        r = auth_owner.get(f'/api/v1/owners/mandates/{relation.id}/pdf/')
        assert r.status_code == status.HTTP_200_OK
        assert r.content.startswith(b'%PDF')

    def test_agent_can_download(self, auth_agent, owner_user, agent_user):
        profile = AgentProfile.objects.get(user=agent_user)
        relation = OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency, status='active',
            contract_start=datetime.date.today(),
        )
        r = auth_agent.get(f'/api/v1/owners/mandates/{relation.id}/pdf/')
        assert r.status_code == status.HTTP_200_OK

    def test_unrelated_user_blocked(self, owner_user, agent_user, create_user):
        profile = AgentProfile.objects.get(user=agent_user)
        relation = OwnerAgentRelation.objects.create(
            owner=owner_user, agent=agent_user, agency=profile.agency, status='active',
            contract_start=datetime.date.today(),
        )
        stranger = create_user(email='mandate_stranger@test.com', phone='+237670000602', role='owner')
        from rest_framework.test import APIClient
        auth_stranger = APIClient()
        auth_stranger.force_authenticate(user=stranger)
        r = auth_stranger.get(f'/api/v1/owners/mandates/{relation.id}/pdf/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_mandate_404(self, auth_agent):
        import uuid
        r = auth_agent.get(f'/api/v1/owners/mandates/{uuid.uuid4()}/pdf/')
        assert r.status_code == status.HTTP_404_NOT_FOUND


class TestTransactionReceiptPDF:

    def test_payer_can_download(self, client_user):
        txn = Transaction.objects.create(
            reference='IH-RCPT-001', payer=client_user, transaction_type='visit_fee',
            amount=5000, platform_fee=100, net_amount=4900,
            status='completed', payment_method='mtn',
        )
        from rest_framework.test import APIClient
        auth_client = APIClient()
        auth_client.force_authenticate(user=client_user)
        r = auth_client.get(f'/api/v1/payments/{txn.id}/receipt/')
        assert r.status_code == status.HTTP_200_OK
        assert r.content.startswith(b'%PDF')

    def test_receiver_can_download(self, client_user, agent_user):
        txn = Transaction.objects.create(
            reference='IH-RCPT-002', payer=client_user, receiver=agent_user,
            transaction_type='visit_fee', amount=5000, platform_fee=100, net_amount=4900,
            status='completed', payment_method='mtn',
        )
        from rest_framework.test import APIClient
        auth_receiver = APIClient()
        auth_receiver.force_authenticate(user=agent_user)
        r = auth_receiver.get(f'/api/v1/payments/{txn.id}/receipt/')
        assert r.status_code == status.HTTP_200_OK

    def test_unrelated_user_blocked(self, client_user, create_user):
        txn = Transaction.objects.create(
            reference='IH-RCPT-003', payer=client_user, transaction_type='visit_fee',
            amount=5000, platform_fee=100, net_amount=4900,
            status='completed', payment_method='mtn',
        )
        stranger = create_user(email='rcpt_stranger@test.com', phone='+237670000603', role='client')
        from rest_framework.test import APIClient
        auth_stranger = APIClient()
        auth_stranger.force_authenticate(user=stranger)
        r = auth_stranger.get(f'/api/v1/payments/{txn.id}/receipt/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_pending_transaction_not_found(self, client_user):
        txn = Transaction.objects.create(
            reference='IH-RCPT-004', payer=client_user, transaction_type='visit_fee',
            amount=5000, status='pending', payment_method='mtn',
        )
        from rest_framework.test import APIClient
        auth_client = APIClient()
        auth_client.force_authenticate(user=client_user)
        r = auth_client.get(f'/api/v1/payments/{txn.id}/receipt/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_agency_colleague_can_download_rent_receipt(
        self, agent_user, owner_user, client_with_agent, property_obj, create_user
    ):
        from apps.agents.services import ensure_agent_profile_and_agency
        from apps.agencies.services import transfer_agent_to_agency
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        txn = Transaction.objects.create(
            reference='IH-RCPT-005', payer=client_with_agent, transaction_type='rent',
            amount=30500, platform_fee=300, net_amount=30000, agency_fee_amount=200,
            status='completed', payment_method='mtn', related_lease_id=payment.lease_id,
        )
        colleague = create_user(email='rcpt_colleague@test.com', phone='+237670000604', role='agent', is_validated=True)
        ensure_agent_profile_and_agency(colleague)
        colleague_profile = AgentProfile.objects.get(user=colleague)
        gerant_profile = AgentProfile.objects.get(user=agent_user)
        transfer_agent_to_agency(colleague_profile, gerant_profile.agency)

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        fresh_colleague = get_user_model().objects.get(pk=colleague.pk)
        auth_colleague = APIClient()
        auth_colleague.force_authenticate(user=fresh_colleague)
        r = auth_colleague.get(f'/api/v1/payments/{txn.id}/receipt/')
        assert r.status_code == status.HTTP_200_OK

    def test_unauthenticated_blocked(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-RCPT-006', payer=client_user, transaction_type='visit_fee',
            amount=5000, status='completed', payment_method='mtn',
        )
        r = api_client.get(f'/api/v1/payments/{txn.id}/receipt/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestLeaseContractPDF:

    def test_tenant_can_download(self, auth_client_with_agent, agent_user, owner_user, client_with_agent, property_obj):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        r = auth_client_with_agent.get(f'/api/v1/contracts/leases/{payment.lease_id}/pdf/')
        assert r.status_code == status.HTTP_200_OK
        assert r.content.startswith(b'%PDF')

    def test_owner_can_download(self, agent_user, owner_user, client_with_agent, property_obj):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        from rest_framework.test import APIClient
        auth_owner = APIClient()
        auth_owner.force_authenticate(user=owner_user)
        r = auth_owner.get(f'/api/v1/contracts/leases/{payment.lease_id}/pdf/')
        assert r.status_code == status.HTTP_200_OK

    def test_unrelated_user_blocked(self, agent_user, owner_user, client_with_agent, property_obj, create_user):
        payment = _paid_payment(agent_user, owner_user, client_with_agent, property_obj)
        stranger = create_user(email='lease_pdf_stranger@test.com', phone='+237670000605', role='client')
        from rest_framework.test import APIClient
        auth_stranger = APIClient()
        auth_stranger.force_authenticate(user=stranger)
        r = auth_stranger.get(f'/api/v1/contracts/leases/{payment.lease_id}/pdf/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_lease_404(self, auth_agent):
        import uuid
        r = auth_agent.get(f'/api/v1/contracts/leases/{uuid.uuid4()}/pdf/')
        assert r.status_code == status.HTTP_404_NOT_FOUND
