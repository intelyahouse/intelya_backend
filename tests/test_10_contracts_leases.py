"""
Tests Contrats et Gestion Locative
Couvre : création baux, paiements loyers, plaintes, renouvellements
"""
import pytest
from datetime import date, timedelta
from rest_framework import status
from unittest.mock import patch

pytestmark = pytest.mark.django_db


class TestContrats:

    def test_agent_voit_ses_contrats(self, auth_agent):
        r = auth_agent.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_client_voit_son_bail(self, auth_client):
        r = auth_client.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_owner_voit_ses_baux(self, auth_owner):
        r = auth_owner.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_agent_cree_bail(self, auth_agent, agent_user, owner_user, client_with_agent, property_obj):
        r = auth_agent.post('/api/v1/contracts/leases/create/', {
            'property': str(property_obj.id),
            'tenant': str(client_with_agent.id),
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=365)).isoformat(),
            'monthly_rent': 150000,
            'deposit_amount': 300000,
            'payment_day': 5,
        })
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_creer_bail(self, auth_client, property_obj):
        r = auth_client.post('/api/v1/contracts/leases/create/', {
            'property': str(property_obj.id),
            'monthly_rent': 150000,
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestGestionLocative:

    def test_voir_paiements_loyer(self, auth_client):
        r = auth_client.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_200_OK

    def test_payer_loyer_mtn(self, auth_client, property_obj):
        mock = {'success': True, 'reference': 'KPAY-RENT-001', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
            r = auth_client.post('/api/v1/payments/initiate/', {
                'amount': '150000',
                'payment_method': 'mtn',
                'phone_number': '+237670000001',
                'related_type': 'rent',
                'related_id': str(property_obj.id),
            })
        assert r.status_code in [200, 201]

    def test_voir_plaintes(self, auth_client):
        r = auth_client.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK

    def test_soumettre_plainte(self, auth_client, property_obj):
        r = auth_client.post('/api/v1/leases/complaints/create/', {
            'property': str(property_obj.id),
            'complaint_type': 'maintenance',
            'title': 'Fuite eau salle de bain',
            'description': 'Il y a une fuite dans la salle de bain depuis 3 jours',
        })
        assert r.status_code in [200, 201]

    def test_non_authentifie_bloque_plainte(self, api_client, property_obj):
        r = api_client.post('/api/v1/leases/complaints/create/', {
            'property': str(property_obj.id),
            'title': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_agent_voit_plaintes_ses_clients(self, auth_agent):
        r = auth_agent.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK

    def test_admin_voit_toutes_plaintes(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/leases/')
        assert r.status_code == status.HTTP_200_OK


class TestAvisEtNotations:

    def test_voir_avis_bien(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/reviews/property/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_avis_agent(self, api_client, agent_user):
        r = api_client.get(f'/api/v1/reviews/agent/{agent_user.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_peut_voir_avis(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/reviews/property/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK
