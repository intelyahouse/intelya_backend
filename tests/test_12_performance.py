"""
Tests Performance et Charge
Couvre : temps de réponse, pagination, requêtes N+1, index DB
"""
import pytest
import time
import uuid
from rest_framework import status
from apps.payments.models import Transaction
from apps.properties.models import Property
from apps.visits.models import VisitRequest
from datetime import date, timedelta

pytestmark = pytest.mark.django_db


class TestTempsReponse:

    def test_liste_biens_sous_2_secondes(self, api_client, property_obj):
        start = time.time()
        r = api_client.get('/api/v1/properties/')
        duration = time.time() - start
        assert r.status_code == status.HTTP_200_OK
        assert duration < 2.0, f"Liste biens trop lente: {duration:.3f}s"

    def test_detail_bien_sous_1_seconde(self, api_client, property_obj):
        start = time.time()
        r = api_client.get(f'/api/v1/properties/{property_obj.id}/')
        duration = time.time() - start
        assert r.status_code == status.HTTP_200_OK
        assert duration < 1.0, f"Détail bien trop lent: {duration:.3f}s"

    def test_connexion_sous_2_secondes(self, api_client, client_user):
        start = time.time()
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        duration = time.time() - start
        assert r.status_code == status.HTTP_200_OK
        assert duration < 2.0, f"Connexion trop lente: {duration:.3f}s"

    def test_profil_sous_1_seconde(self, auth_client):
        start = time.time()
        r = auth_client.get('/api/v1/users/me/')
        duration = time.time() - start
        assert r.status_code == status.HTTP_200_OK
        assert duration < 1.0, f"Profil trop lent: {duration:.3f}s"

    def test_health_check_sous_500ms(self, api_client):
        start = time.time()
        r = api_client.get('/api/health/')
        duration = time.time() - start
        assert r.status_code == status.HTTP_200_OK
        assert duration < 0.5, f"Health check trop lent: {duration:.3f}s"

    def test_10_requetes_consecutives_rapides(self, api_client):
        start = time.time()
        for _ in range(10):
            api_client.get('/api/v1/properties/')
        duration = time.time() - start
        assert duration < 10.0, f"10 requêtes trop lentes: {duration:.3f}s"


class TestPagination:

    def test_pagination_par_defaut(self, api_client):
        r = api_client.get('/api/v1/properties/')
        assert r.status_code == status.HTTP_200_OK
        assert 'count' in r.data
        assert 'results' in r.data
        assert 'next' in r.data
        assert 'previous' in r.data

    def test_pagination_page_1(self, api_client):
        r = api_client.get('/api/v1/properties/?page=1&page_size=5')
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data['results']) <= 5

    def test_pagination_page_inexistante(self, api_client):
        r = api_client.get('/api/v1/properties/?page=99999')
        assert r.status_code in [200, 404]

    def test_pagination_transactions(self, auth_client, client_user):
        for i in range(15):
            Transaction.objects.create(
                reference=f'IH-PAG-{i:03d}', payer=client_user,
                transaction_type='visit', amount=5000,
                platform_fee=100, net_amount=4900,
                currency='FCFA', status='completed', payment_method='mtn',
            )
        r = auth_client.get('/api/v1/payments/history/?page=1&page_size=10')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['count'] >= 15
        assert len(r.data['results']) <= 10

    def test_pagination_notifications(self, auth_client):
        r = auth_client.get('/api/v1/notifications/?page=1')
        assert r.status_code == status.HTTP_200_OK


class TestIndex:

    def test_recherche_par_ville_indexee(self, api_client, property_obj):
        start = time.time()
        for _ in range(5):
            api_client.get('/api/v1/properties/?city=Douala')
        duration = time.time() - start
        assert duration < 3.0

    def test_transactions_indexees(self, auth_client, client_user):
        for i in range(20):
            Transaction.objects.create(
                reference=f'IH-IDX2-{i:03d}', payer=client_user,
                transaction_type='visit', amount=5000,
                platform_fee=100, net_amount=4900,
                currency='FCFA', status='completed', payment_method='mtn',
            )
        start = time.time()
        auth_client.get('/api/v1/payments/history/')
        duration = time.time() - start
        assert duration < 2.0

    def test_visites_indexees(self, auth_agent, agent_user, client_with_agent, property_obj):
        for i in range(10):
            VisitRequest.objects.create(
                client=client_with_agent,
                agent=agent_user,
                visit_property=property_obj,
                status='pending',
            )
        start = time.time()
        auth_agent.get('/api/v1/visits/')
        duration = time.time() - start
        assert duration < 2.0
