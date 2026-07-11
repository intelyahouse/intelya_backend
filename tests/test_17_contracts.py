"""
Tests Contrats — Baux et Contrats Agent-Owner
"""
import pytest
from datetime import date, timedelta
from rest_framework import status
from apps.contracts.models import LeaseContract

pytestmark = pytest.mark.django_db


class TestBaux:

    def test_agent_cree_bail(self, auth_agent, agent_user, owner_user, client_with_agent, property_obj):
        r = auth_agent.post('/api/v1/contracts/leases/create/', {
            'tenant': str(client_with_agent.id),
            'owner': str(owner_user.id),
            'rental_property': str(property_obj.id),
            'monthly_rent': 150000,
            'deposit_amount': 300000,
            'agent_commission': 15000,
            'commission_before_rent': True,
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=365)).isoformat(),
            'payment_day': 5,
        })
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_creer_bail(self, auth_client, owner_user, client_with_agent, property_obj):
        r = auth_client.post('/api/v1/contracts/leases/create/', {
            'tenant': str(client_with_agent.id),
            'monthly_rent': 150000,
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.post('/api/v1/contracts/leases/create/', {})
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_voir_mes_baux_agent(self, auth_agent):
        r = auth_agent.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_mes_baux_client(self, auth_client):
        r = auth_client.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_mes_baux_owner(self, auth_owner):
        r = auth_owner.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_signer_bail_agent(self, auth_client_with_agent, agent_user, owner_user, client_with_agent, property_obj):
        bail = LeaseContract.objects.create(
            tenant=client_with_agent,
            owner=owner_user,
            agent=agent_user,
            rental_property=property_obj,
            monthly_rent=150000,
            deposit_amount=300000,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            payment_day=5,
            status='draft',
        )
        r = auth_client_with_agent.post(f'/api/v1/contracts/leases/{bail.id}/sign/')
        assert r.status_code in [200, 201]

    def test_signer_bail_owner(self, auth_owner, agent_user, owner_user, client_with_agent, property_obj):
        bail = LeaseContract.objects.create(
            tenant=client_with_agent,
            owner=owner_user,
            agent=agent_user,
            rental_property=property_obj,
            monthly_rent=150000,
            deposit_amount=300000,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            payment_day=5,
            status='draft',
        )
        r = auth_owner.post(f'/api/v1/contracts/leases/{bail.id}/sign/')
        assert r.status_code in [200, 201]

    def test_bail_integralement_signe(self, agent_user, owner_user, client_with_agent, property_obj):
        bail = LeaseContract.objects.create(
            tenant=client_with_agent,
            owner=owner_user,
            agent=agent_user,
            rental_property=property_obj,
            monthly_rent=150000,
            deposit_amount=300000,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            payment_day=5,
            signed_by_tenant=True,
            signed_by_owner=True,
        )
        assert bail.signed_by_tenant is True
        assert bail.signed_by_owner is True

    def test_bail_partiellement_signe(self, agent_user, owner_user, client_with_agent, property_obj):
        bail = LeaseContract.objects.create(
            tenant=client_with_agent,
            owner=owner_user,
            agent=agent_user,
            rental_property=property_obj,
            monthly_rent=150000,
            deposit_amount=300000,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            payment_day=5,
            signed_by_tenant=True,
            signed_by_owner=False,
        )
        assert bail.signed_by_owner is False

    def test_admin_voit_tous_baux(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/leases/')
        assert r.status_code == status.HTTP_200_OK
