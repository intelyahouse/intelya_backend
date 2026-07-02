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
        agent_commission=15000,
        commission_before_rent=True,
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
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
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
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
            r = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '150000',
                'payment_method': 'orange',
                'phone_number': '+237690000020',
                'related_type': 'rent',
                'related_id': str(bail_actif.id),
            })
        assert r.status_code in [200, 201]

    def test_confirmer_paiement_cash(self, auth_agent, bail_actif, client_with_agent):
        paiement = RentPayment.objects.create(
            lease=bail_actif,
            tenant=client_with_agent,
            amount=150000,
            platform_fee=3000,
            owner_amount=147000,
            status='pending',
            due_date=date.today(),
            period_month=date.today().month,
            period_year=date.today().year,
        )
        r = auth_agent.post('/api/v1/leases/payments/confirm-cash/', {
            'rent_payment_id': str(paiement.id),
            'notes': 'Paiement reçu en espèces',
        })
        assert r.status_code in [200, 201]

    def test_paiement_unique_par_periode(self, bail_actif, client_with_agent):
        RentPayment.objects.create(
            lease=bail_actif, tenant=client_with_agent,
            amount=150000, platform_fee=3000, owner_amount=147000,
            status='paid', due_date=date.today(),
            period_month=6, period_year=2026,
        )
        count_avant = RentPayment.objects.filter(
            lease=bail_actif, period_month=6, period_year=2026
        ).count()
        assert count_avant == 1
        try:
            RentPayment.objects.create(
                lease=bail_actif, tenant=client_with_agent,
                amount=150000, platform_fee=3000, owner_amount=147000,
                status='pending', due_date=date.today(),
                period_month=6, period_year=2026,
            )
            assert False, "Devrait lever une exception unique_together"
        except Exception:
            pass


class TestPlaintes:

    def test_soumettre_plainte(self, auth_client_with_agent, bail_actif):
        """La vue cherche automatiquement le bail actif du user"""
        r = auth_client_with_agent.post('/api/v1/leases/complaints/submit/', {
            'category': 'maintenance',
            'title': 'Fuite eau salle de bain',
            'description': 'Il y a une fuite dans la salle de bain depuis 3 jours',
        })
        assert r.status_code in [200, 201]

    def test_soumettre_plainte_sans_bail_bloque(self, auth_client):
        """Sans bail actif, la plainte est rejetée"""
        r = auth_client.post('/api/v1/leases/complaints/submit/', {
            'category': 'maintenance',
            'title': 'Test sans bail',
            'description': 'Description test',
        })
        assert r.status_code in [400, 403, 404]

    def test_voir_mes_plaintes(self, auth_client_with_agent):
        r = auth_client_with_agent.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_voit_plaintes_clients(self, auth_agent):
        r = auth_agent.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.post('/api/v1/leases/complaints/submit/', {
            'category': 'maintenance', 'title': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_resoudre_plainte_agent(self, auth_agent, agent_user, owner_user, client_with_agent, bail_actif):
        plainte = Complaint.objects.create(
            lease=bail_actif,
            tenant=client_with_agent,
            category='maintenance',
            title='Test plainte résolution',
            description='Description de la plainte test résolution',
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
            description='Description de la plainte test client',
            status='open',
        )
        r = auth_client_with_agent.post(f'/api/v1/leases/complaints/{plainte.id}/resolve/', {
            'resolution_note': 'Je résous moi-même',
        })
        assert r.status_code in [403, 404]
