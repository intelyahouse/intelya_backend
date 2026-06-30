"""
Tests Litiges Complets et Avis
"""
import pytest
from rest_framework import status
from apps.disputes.models import Dispute, Report
from apps.reviews.models import Review
from apps.visits.models import VisitRequest

pytestmark = pytest.mark.django_db


class TestLitigesComplets:

    def test_creer_litige(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'visit',
            'title': 'Agent absent lors de la visite',
            'description': 'L\'agent ne s\'est pas présenté à la visite planifiée',
        })
        assert r.status_code in [200, 201]

    def test_creer_litige_paiement(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'payment',
            'title': 'Double facturation',
            'description': 'J\'ai été facturé deux fois pour la même visite',
        })
        assert r.status_code in [200, 201]

    def test_voir_mes_litiges(self, auth_client):
        r = auth_client.get('/api/v1/disputes/disputes/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/disputes/disputes/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_repondre_litige(self, auth_agent, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='visit',
            title='Test litige',
            description='Description du litige test',
            status='open',
        )
        r = auth_agent.post(f'/api/v1/disputes/disputes/{litige.id}/respond/', {
            'response': 'Je conteste cette accusation',
        })
        assert r.status_code in [200, 201]

    def test_admin_decide_litige_claimant_wins(self, auth_admin, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='visit',
            title='Test admin litige 1',
            description='Description du litige test admin',
            status='open',
        )
        r = auth_admin.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'claimant_wins',
            'decision_note': 'Le plaignant a raison',
        })
        assert r.status_code in [200, 201]

    def test_admin_decide_litige_defendant_wins(self, auth_admin, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='payment',
            title='Test admin litige 2',
            description='Description du litige test admin 2',
            status='open',
        )
        r = auth_admin.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'defendant_wins',
            'decision_note': 'Le défendeur a raison',
        })
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_decider_litige(self, auth_client, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='visit',
            title='Test client decide',
            description='Test',
            status='open',
        )
        r = auth_client.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'claimant_wins',
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestSignalements:

    def test_creer_signalement(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'harassment',
            'description': 'Cet agent me harcèle avec des appels',
        })
        assert r.status_code in [200, 201]

    def test_admin_voit_signalements(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/reports/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client, agent_user):
        r = api_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'fraud', 'description': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_trois_signalements_enregistres(self, client_user, agent_user, create_user):
        for i, phone in enumerate(['+237670000060', '+237670000061', '+237670000062']):
            s = create_user(email=f's{i}@test.cm', phone=phone, role='client')
            Report.objects.create(
                reporter=s, reported=agent_user,
                reason='fraud', description='Test signalement',
            )
        assert Report.objects.filter(reported=agent_user).count() >= 3


class TestAvis:

    def test_voir_avis_bien_public(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/reviews/property/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_avis_agent_public(self, api_client, agent_user):
        r = api_client.get(f'/api/v1/reviews/agent/{agent_user.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_laisser_avis_apres_visite_gps(self, auth_client_with_agent, client_with_agent, property_obj, agent_user):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=agent_user,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'agent_rating': 5,
            'agent_comment': 'Agent très professionnel',
            'property_rating': 4,
            'property_comment': 'Bien conforme',
        })
        assert r.status_code in [200, 201]

    def test_avis_sans_gps_refuse(self, auth_client_with_agent, client_with_agent, property_obj, agent_user):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=agent_user,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=False,
        )
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'agent_rating': 5, 'agent_comment': 'Test',
        })
        assert r.status_code in [400, 404]

    def test_note_invalide_rejetee(self, auth_client_with_agent, client_with_agent, property_obj, agent_user):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=agent_user,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'agent_rating': 10,
            'agent_comment': 'Note invalide',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_authentifie_bloque(self, api_client, property_obj):
        import uuid
        r = api_client.post(f'/api/v1/reviews/leave/{uuid.uuid4()}/', {
            'agent_rating': 5,
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
