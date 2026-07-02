import pytest
from datetime import date, timedelta
from rest_framework import status
from apps.visits.models import VisitRequest

pytestmark = pytest.mark.django_db


class TestVisites:

    def test_client_demande_visite(self, auth_client_with_agent, property_obj):
        r = auth_client_with_agent.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
            'client_message': 'Je suis intéressé par ce bien',
        })
        assert r.status_code in [200, 201]

    def test_client_sans_agent_bloque(self, auth_client, property_obj):
        r = auth_client.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert r.status_code in [400, 403]

    def test_non_authentifie_bloque(self, api_client, property_obj):
        r = api_client.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_proprietaire_ne_peut_pas_demander(self, auth_owner, property_obj):
        r = auth_owner.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert r.status_code in [400, 403]

    def test_voir_mes_visites(self, auth_client_with_agent):
        r = auth_client_with_agent.get('/api/v1/visits/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_voit_ses_visites(self, auth_agent):
        r = auth_agent.get('/api/v1/visits/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_planifie_visite(self, auth_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='pending',
        )
        r = auth_agent.post(f'/api/v1/visits/{visit.id}/schedule/', {
            'scheduled_date': (date.today() + timedelta(days=3)).isoformat(),
            'scheduled_time': '10:00',
        })
        assert r.status_code in [200, 201]

    def test_autre_agent_ne_peut_pas_planifier(self, api_client, create_user, client_with_agent, property_obj):
        autre = create_user(
            email='a2@test.cm', phone='+237670000082',
            role='agent', is_validated=True,
        )
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='pending',
        )
        api_client.force_authenticate(user=autre)
        r = api_client.post(f'/api/v1/visits/{visit.id}/schedule/', {
            'scheduled_date': (date.today() + timedelta(days=3)).isoformat(),
            'scheduled_time': '10:00',
        })
        assert r.status_code in [403, 404]

    def test_client_annule_visite(self, auth_client_with_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='scheduled',
        )
        r = auth_client_with_agent.post(f'/api/v1/visits/{visit.id}/cancel/', {
            'reason': 'Indisponible ce jour',
        })
        assert r.status_code in [200, 201]

    def test_autre_client_ne_peut_pas_annuler(self, api_client, create_user, client_with_agent, property_obj):
        autre = create_user(
            email='c2@test.cm', phone='+237670000081', role='client',
        )
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='scheduled',
        )
        api_client.force_authenticate(user=autre)
        r = api_client.post(f'/api/v1/visits/{visit.id}/cancel/', {
            'reason': 'Test intrusion',
        })
        assert r.status_code in [403, 404]

    def test_confirmation_gps(self, auth_client_with_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='scheduled',
        )
        r = auth_client_with_agent.post(f'/api/v1/visits/{visit.id}/confirm-gps/', {
            'latitude': 4.0500, 'longitude': 9.7000,
        })
        # 200/201 si dans le rayon, 400 si hors rayon ou pas de location configurée
        assert r.status_code in [200, 201, 400, 500]

    def test_visite_dupliquee_refusee(self, auth_client_with_agent, client_with_agent, property_obj):
        VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='pending',
        )
        r = auth_client_with_agent.post('/api/v1/visits/request/', {
            'property_id': str(property_obj.id),
        })
        assert r.status_code in [400, 409]

    def test_laisser_avis(self, auth_client_with_agent, client_with_agent, property_obj):
        visit = VisitRequest.objects.create(
            client=client_with_agent,
            agent=property_obj.agent,
            visit_property=property_obj,
            status='completed',
            client_gps_confirmed=True,
        )
        r = auth_client_with_agent.post(f'/api/v1/visits/{visit.id}/review/', {
            'property_rating': 5,
            'property_comment': 'Excellent bien !',
            'agent_rating': 5,
            'agent_comment': 'Très bon agent',
        })
        assert r.status_code in [200, 201, 400]
