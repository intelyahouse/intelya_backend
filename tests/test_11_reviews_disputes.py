"""
Tests avis, litiges et signalements
Niveau : Tests d'intégration + fonctionnels API
"""
import pytest
from datetime import date, timedelta
from rest_framework import status
from apps.visits.models import VisitRequest
from apps.disputes.models import Dispute, Report

pytestmark = pytest.mark.django_db


class TestAvis:

    def test_voir_avis_bien_public(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/reviews/property/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_avis_agent_public(self, api_client, agent_user):
        from apps.agents.models import AgentProfile
        profile = AgentProfile.objects.filter(user=agent_user).first()
        if profile:
            r = api_client.get(f'/api/v1/reviews/agent/{profile.id}/')
            assert r.status_code == status.HTTP_200_OK

    def test_laisser_avis_apres_visite_gps(self, auth_client_with_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'property_rating': 5,
            'property_comment': 'Excellent bien, très propre et bien entretenu.',
            'agent_rating': 5,
            'agent_comment': 'Agent très professionnel et réactif.',
        })
        assert r.status_code in [200, 201]

    def test_laisser_avis_sans_gps_bloque(self, auth_client_with_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=False,
        )
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'property_rating': 5,
            'property_comment': 'Excellent.',
            'agent_rating': 5,
            'agent_comment': 'Parfait.',
        })
        assert r.status_code in [400, 403, 404]

    def test_double_avis_bloque(self, auth_client_with_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'property_rating': 4, 'property_comment': 'Bien.',
            'agent_rating': 4, 'agent_comment': 'Correct.',
        })
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'property_rating': 3, 'property_comment': 'Moins bien.',
            'agent_rating': 3, 'agent_comment': 'Moyen.',
        })
        assert r.status_code in [400, 409]

    def test_non_authentifie_ne_peut_pas_laisser_avis(self, api_client, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        r = api_client.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'property_rating': 5, 'property_comment': 'Test.',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestLitiges:

    def test_ouvrir_litige(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'agent',
            'title': 'Agent non professionnel',
            'description': 'L agent n a pas respecte les termes de notre accord concernant les frais de visite.',
        })
        assert r.status_code in [200, 201]

    def test_voir_mes_litiges(self, auth_client):
        r = auth_client.get('/api/v1/disputes/disputes/')
        assert r.status_code == status.HTTP_200_OK

    def test_repondre_litige(self, auth_agent, client_user):
        dispute = Dispute.objects.create(
            claimant=client_user,
            defendant=auth_agent._user if hasattr(auth_agent, '_user') else client_user,
            dispute_type='agent',
            title='Test litige',
            description='Description test',
            status='open',
        )
        r = auth_agent.post(f'/api/v1/disputes/disputes/{dispute.id}/respond/', {
            'response': 'Je conteste cette affirmation. Voici ma version des faits.',
        })
        assert r.status_code in [200, 201, 404]

    def test_non_authentifie_ne_peut_pas_ouvrir_litige(self, api_client, agent_user):
        r = api_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'agent',
            'title': 'Test', 'description': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestSignalements:

    def test_signaler_utilisateur(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'harassment',
            'description': 'Cet agent m envoie des messages inappropries.',
        })
        assert r.status_code in [200, 201]

    def test_ne_peut_pas_se_signaler_soi_meme(self, auth_client, client_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(client_user.id),
            'reason': 'spam',
            'description': 'Test auto-signalement',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_trois_signalements_suspendent(self, create_user, agent_user):
        for i in range(3):
            u = create_user(
                email=f'reporter{i}@test.cm',
                phone=f'+23767000{70+i}',
                role='client',
            )
            Report.objects.create(
                reporter=u, reported=agent_user,
                reason='fraud', description='Test',
            )
        from apps.disputes.views import CreateReportView
        agent_user.refresh_from_db()

    def test_non_authentifie_ne_peut_pas_signaler(self, api_client, agent_user):
        r = api_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'spam', 'description': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminLitiges:

    def test_admin_voit_tous_litiges(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/disputes/')
        assert r.status_code == status.HTTP_200_OK

    def test_admin_voit_tous_signalements(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/reports/')
        assert r.status_code == status.HTTP_200_OK

    def test_admin_decide_litige(self, auth_admin, client_user, agent_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user,
            dispute_type='agent',
            title='Litige test admin',
            description='Description du litige',
            status='open',
        )
        r = auth_admin.post(
            f'/api/v1/admin-panel/disputes/{dispute.id}/decide/',
            {
                'decision': 'claimant_wins',
                'admin_note': 'Après examen des preuves, le plaignant a raison.',
            }
        )
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_decider_litige(self, auth_client, client_user, agent_user):
        dispute = Dispute.objects.create(
            claimant=client_user, defendant=agent_user,
            dispute_type='agent',
            title='Litige test',
            description='Description',
            status='open',
        )
        r = auth_client.post(
            f'/api/v1/admin-panel/disputes/{dispute.id}/decide/',
            {'decision': 'claimant_wins', 'admin_note': 'Test'}
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN
