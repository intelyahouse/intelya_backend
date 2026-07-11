"""
Tests Litiges Complets et Avis
"""
import pytest
from rest_framework import status
from apps.disputes.models import Dispute, Report
from apps.reviews.models import Review
from apps.visits.models import VisitRequest
from apps.payments.models import Transaction, Escrow
from django.utils import timezone
from datetime import timedelta, date

pytestmark = pytest.mark.django_db


class TestLitigesComplets:

    def test_creer_litige_visite(self, auth_client, agent_user):
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

    def test_creer_litige_bien(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'property',
            'title': 'Bien non conforme',
            'description': 'Le bien ne correspond pas à la description de l\'annonce',
        })
        assert r.status_code in [200, 201]

    def test_voir_mes_litiges(self, auth_client):
        r = auth_client.get('/api/v1/disputes/disputes/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/disputes/disputes/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_repondre_litige_defendeur(self, auth_agent, client_user, agent_user):
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

    def test_admin_resout_litige_plaignant_gagne(self, auth_admin, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='visit',
            title='Test litige admin',
            description='Description du litige test admin resolution',
            status='open',
        )
        r = auth_admin.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'claimant_wins',
            'decision_note': 'Les preuves confirment la présence du client',
        })
        assert r.status_code in [200, 201]

    def test_admin_resout_litige_defendeur_gagne(self, auth_admin, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='payment',
            title='Test litige agent gagne',
            description='Description test resolution defendeur gagne',
            status='open',
        )
        r = auth_admin.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'defendant_wins',
            'decision_note': 'Le paiement est légitime',
        })
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_resoudre_litige(self, auth_client, client_user, agent_user):
        litige = Dispute.objects.create(
            claimant=client_user,
            defendant=agent_user,
            dispute_type='visit',
            title='Test',
            description='Test description litige resolution',
            status='open',
        )
        r = auth_client.post(f'/api/v1/admin-panel/disputes/{litige.id}/decide/', {
            'decision': 'claimant_wins',
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestSignalements:

    def test_creer_signalement_harcelement(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'harassment',
            'description': 'Cet agent me harcèle avec des appels non sollicités',
        })
        assert r.status_code in [200, 201]

    def test_creer_signalement_fraude(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'fraud',
            'description': 'Cet agent a encaissé de l\'argent sans fournir le service',
        })
        assert r.status_code in [200, 201]

    def test_creer_signalement_fausse_info(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'fake_info',
            'description': 'Les photos du bien ne correspondent pas à la réalité',
        })
        assert r.status_code in [200, 201]

    def test_admin_voit_signalements(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/reports/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_ne_peut_pas_signaler(self, api_client, agent_user):
        r = api_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'harassment',
            'description': 'Test',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_trois_signalements_model(self, client_user, agent_user, create_user):
        s1 = create_user(email='s1@test.cm', phone='+237670000060', role='client')
        s2 = create_user(email='s2@test.cm', phone='+237670000061', role='client')
        s3 = create_user(email='s3@test.cm', phone='+237670000062', role='client')
        for signaleur in [s1, s2, s3]:
            Report.objects.create(
                reporter=signaleur, reported=agent_user,
                reason='fraud', description='Test signalement comptage',
            )
        count = Report.objects.filter(reported=agent_user).count()
        assert count >= 3


class TestAvis:

    def test_voir_avis_bien_public(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/reviews/property/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_avis_agent_public(self, api_client, agent_user):
        r = api_client.get(f'/api/v1/reviews/agent/{agent_user.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_laisser_avis_apres_visite(self, auth_client_with_agent, client_with_agent, property_obj, agent_user):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=agent_user,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        r = auth_client_with_agent.post(f'/api/v1/reviews/leave/{visit.id}/', {
            'agent_rating': 5,
            'agent_comment': 'Agent très professionnel et ponctuel',
            'property_rating': 4,
            'property_comment': 'Bien conforme à la description',
        })
        assert r.status_code in [200, 201]

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
            'agent_comment': 'Note invalide supérieure à 5',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_avis_model_score(self, client_user, agent_user, property_obj):
        review = Review.objects.create(
            reviewer=client_user,
            agent=agent_user,
            rental_property=property_obj,
            agent_rating=5,
            agent_comment='Excellent agent très sérieux',
            property_rating=4,
            property_comment='Très beau bien bien entretenu',
            gps_verified=True,
        )
        assert review.agent_rating == 5
        assert review.property_rating == 4
        assert review.gps_verified is True

    def test_non_authentifie_ne_peut_pas_laisser_avis(self, api_client):
        import uuid
        r = api_client.post(f'/api/v1/reviews/leave/{uuid.uuid4()}/', {
            'agent_rating': 5, 'agent_comment': 'Test non auth',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
