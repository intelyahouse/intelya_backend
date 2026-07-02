"""
Tests End-to-End — Scénarios complets de production
"""
import pytest
from datetime import date, timedelta
from rest_framework import status
from unittest.mock import patch
from apps.visits.models import VisitRequest
from apps.contracts.models import LeaseContract
from apps.disputes.models import Dispute

pytestmark = pytest.mark.django_db


class TestScenarioClientComplet:

    def test_01_inscription(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Kouam', 'last_name': 'Eric',
            'email': 'kouam@test.cm', 'phone': '+237670088888',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        assert r.status_code == status.HTTP_201_CREATED

    def test_02_login(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        assert r.status_code == status.HTTP_200_OK
        assert 'access' in r.data['data']

    def test_03_chercher_bien(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?city=Douala')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['count'] >= 1

    def test_04_detail_sans_adresse(self, auth_client, property_obj):
        r = auth_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data.get('data', r.data)
        assert data.get('full_address') in [None, '', 'Non disponible', 'Adresse confidentielle']

    def test_05_liker_bien(self, auth_client, property_obj):
        r = auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert r.status_code in [200, 201]

    def test_06_demander_visite(self, auth_client_with_agent, property_obj):
        r = auth_client_with_agent.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
            'client_message': 'Très intéressé',
        })
        assert r.status_code in [200, 201]

    def test_07_payer_visite(self, auth_client_with_agent, property_obj):
        mock = {'success': True, 'reference': 'KPAY-E2E-001', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
            r = auth_client_with_agent.post('/api/v1/payments/initiate/', {
                'amount': '5000', 'payment_method': 'mtn',
                'phone_number': '+237670000020',
                'related_type': 'visit', 'related_id': str(property_obj.id),
            })
        assert r.status_code in [200, 201]

    def test_08_voir_favoris(self, auth_client, property_obj):
        auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        r = auth_client.get('/api/v1/properties/favorites/')
        assert r.status_code == status.HTTP_200_OK

    def test_09_voir_notifications(self, auth_client_with_agent):
        r = auth_client_with_agent.get('/api/v1/notifications/')
        assert r.status_code == status.HTTP_200_OK


class TestScenarioAgentComplet:

    def test_01_voir_biens(self, auth_agent):
        r = auth_agent.get('/api/v1/properties/agent/')
        assert r.status_code == status.HTTP_200_OK

    def test_02_voir_visites(self, auth_agent):
        r = auth_agent.get('/api/v1/visits/')
        assert r.status_code == status.HTTP_200_OK

    def test_03_planifier_visite(self, auth_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent, agent=property_obj.agent,
            visit_property=property_obj, status='pending',
        )
        r = auth_agent.post(f'/api/v1/visits/{visit.id}/schedule/', {
            'scheduled_date': (date.today() + timedelta(days=2)).isoformat(),
            'scheduled_time': '10:00',
        })
        assert r.status_code in [200, 201]

    def test_04_cree_bail(self, auth_agent, agent_user, owner_user, client_with_agent, property_obj):
        r = auth_agent.post('/api/v1/contracts/leases/create/', {
            'tenant': str(client_with_agent.id),
            'owner': str(owner_user.id),
            'rental_property': str(property_obj.id),
            'monthly_rent': 150000, 'deposit_amount': 300000,
            'agent_commission': 15000, 'commission_before_rent': True,
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=365)).isoformat(),
            'payment_day': 5,
        })
        assert r.status_code in [200, 201]

    def test_05_booster_annonce(self, auth_agent):
        mock = {'success': True, 'reference': 'KPAY-E2E-B01', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
            r = auth_agent.post('/api/v1/boost/activate/', {
                'level': 'bronze', 'duration_days': 7,
                'target_city': 'Douala', 'payment_method': 'mtn',
                'phone_number': '+237670000002',
            })
        assert r.status_code in [200, 201]


class TestScenarioAdminComplet:

    def test_01_voir_stats(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_200_OK

    def test_02_voir_utilisateurs(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/users/')
        assert r.status_code == status.HTTP_200_OK

    def test_03_valider_agent(self, auth_admin, agent_user):
        agent_user.is_validated = False
        agent_user.validation_status = 'pending'
        agent_user.save()
        r = auth_admin.post(f'/api/v1/admin-panel/users/{agent_user.id}/validate/', {
            'action': 'approve',
        })
        assert r.status_code in [200, 201]

    def test_04_voir_transactions(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/transactions/')
        assert r.status_code == status.HTTP_200_OK

    def test_05_arbitrer_litige(self, auth_admin, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user, defendant=agent_user,
            dispute_type='visit', title='Litige E2E',
            description='Description litige end to end test',
            status='open',
        )
        r = auth_admin.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'claimant_wins',
            'decision_note': 'Le client a raison',
        })
        assert r.status_code in [200, 201]

    def test_06_voir_revenus(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/revenue/')
        assert r.status_code == status.HTTP_200_OK


class TestScenarioOwnerComplet:

    def test_01_voir_profil(self, auth_owner):
        r = auth_owner.get('/api/v1/owners/me/')
        assert r.status_code == status.HTTP_200_OK

    def test_02_voir_son_agent(self, auth_owner):
        r = auth_owner.get('/api/v1/owners/me/agent/')
        assert r.status_code == status.HTTP_200_OK

    def test_03_voir_revenus(self, auth_owner):
        r = auth_owner.get('/api/v1/payments/history/')
        assert r.status_code == status.HTTP_200_OK

    def test_04_mettre_a_jour_compte_bancaire(self, auth_owner):
        r = auth_owner.patch('/api/v1/owners/me/bank-accounts/', {
            'mtn_momo_number': '+237670000003',
        })
        assert r.status_code in [200, 201]
