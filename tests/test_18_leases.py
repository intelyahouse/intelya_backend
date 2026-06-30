"""
Tests Gestion Locative — Loyers, Plaintes, Dettes
"""
import pytest
from datetime import date, timedelta
from rest_framework import status
from unittest.mock import patch
from apps.contracts.models import LeaseContract
from apps.leases.models import RentPayment, Complaint

pytestmark = pytest.mark.django_db


@pytest.fixture
def bail_actif(agent_user, owner_user, client_with_agent, property_obj):
    return LeaseContract.objects.create(
        tenant=client_with_agent,
        owner=owner_user,
        agent=agent_user,
        rental_property=property_obj,
        monthly_rent=150000,
        deposit_amount=300000,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=335),
        payment_day=5,
        status='active',
        signed_by_tenant=True,
        signed_by_owner=True,
    )


class TestPaiementsLoyer:

    def test_voir_paiements_loyer_client(self, auth_client_with_agent):
        r = auth_client_with_agent.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_paiements_loyer_agent(self, auth_agent):
        r = auth_agent.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_paiements_loyer_owner(self, auth_owner):
        r = auth_owner.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_payer_loyer_mtn(self, auth_client_with_agent, bail_actif):
        mock = {'success': True, 'reference': 'KPAY-LOYER-001', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.views.kpay_service.collect', return_value=mock):
            r = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '150000',
                'payment_method': 'mtn',
                'phone_number': '+237670000020',
                'related_type': 'rent',
                'related_id': str(bail_actif.id),
            })
        assert r.status_code in [200, 201]

    def test_payer_loyer_orange(self, auth_client_with_agent, bail_actif):
        mock = {'success': True, 'reference': 'KPAY-LOYER-002', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.views.kpay_service.collect', return_value=mock):
            r = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '150000',
                'payment_method': 'orange',
                'phone_number': '+237690000020',
                'related_type': 'rent',
                'related_id': str(bail_actif.id),
            })
        assert r.status_code in [200, 201]

    def test_confirmer_paiement_cash(self, auth_agent, bail_actif, client_with_agent):
        from datetime import date as d
        paiement = RentPayment.objects.create(
            lease=bail_actif,
            tenant=client_with_agent,
            amount=150000,
            platform_fee=3000,
            owner_amount=147000,
            status='pending',
            due_date=d.today(),
            period_month=d.today().month,
            period_year=d.today().year,
        )
        r = auth_agent.post('/api/v1/leases/payments/confirm-cash/', {
            'rent_payment_id': str(paiement.id),
            'notes': 'Paiement reçu en espèces',
        })
        assert r.status_code in [200, 201]

    def test_paiement_cree_avec_bon_montant(self, bail_actif, client_with_agent):
        from datetime import date as d
        paiement = RentPayment.objects.create(
            lease=bail_actif,
            tenant=client_with_agent,
            amount=150000,
            platform_fee=3000,
            owner_amount=147000,
            status='pending',
            due_date=d.today(),
            period_month=d.today().month,
            period_year=d.today().year,
        )
        assert float(paiement.amount) == 150000
        assert float(paiement.platform_fee) == 3000
        assert float(paiement.owner_amount) == 147000


class TestPlaintes:

    def test_soumettre_plainte(self, auth_client_with_agent, bail_actif, owner_user):
        r = auth_client_with_agent.post('/api/v1/leases/complaints/submit/', {
            'category': 'maintenance',
            'title': 'Fuite eau salle de bain',
            'description': 'Il y a une fuite dans la salle de bain depuis 3 jours',
        })
        assert r.status_code in [200, 201]

    def test_voir_mes_plaintes(self, auth_client_with_agent):
        r = auth_client_with_agent.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_voit_plaintes_clients(self, auth_agent):
        r = auth_agent.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque_plainte(self, api_client):
        r = api_client.post('/api/v1/leases/complaints/submit/', {
            'category': 'maintenance', 'title': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_resoudre_plainte_agent(self, auth_agent, agent_user, owner_user, client_with_agent, bail_actif):
        plainte = Complaint.objects.create(
            lease=bail_actif,
            tenant=client_with_agent,
            assigned_to=agent_user,
            category='maintenance',
            title='Test plainte',
            description='Description de la plainte test resolution',
            status='open',
        )
        r = auth_agent.post(f'/api/v1/leases/complaints/{plainte.id}/resolve/', {
            'resolution_note': 'Problème réparé par le plombier',
        })
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_resoudre(self, auth_client_with_agent, client_with_agent, bail_actif):
        plainte = Complaint.objects.create(
            lease=bail_actif,
            tenant=client_with_agent,
            category='maintenance',
            title='Test plainte client',
            description='Description de la plainte test client resolution',
            status='open',
        )
        r = auth_client_with_agent.post(f'/api/v1/leases/complaints/{plainte.id}/resolve/', {
            'resolution_note': 'Je résous moi-même',
        })
        assert r.status_code in [403, 404]
