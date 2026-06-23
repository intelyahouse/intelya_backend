"""
Tests de performance et de charge
Niveau : Tests non-fonctionnels production
"""
import pytest
import time
import uuid
import threading
from rest_framework import status
from apps.payments.models import Transaction
from apps.properties.models import Property

pytestmark = pytest.mark.django_db(transaction=True)


class TestTempsReponse:
    """Tous les endpoints doivent répondre en moins de 2 secondes"""

    def test_liste_biens_rapide(self, api_client, property_obj):
        start = time.time()
        api_client.get('/api/v1/properties/')
        assert time.time() - start < 2.0, "Liste biens trop lente"

    def test_detail_bien_rapide(self, api_client, property_obj):
        start = time.time()
        api_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert time.time() - start < 2.0

    def test_login_rapide(self, api_client, client_user):
        start = time.time()
        api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!'
        })
        assert time.time() - start < 2.0

    def test_profil_rapide(self, auth_client):
        start = time.time()
        auth_client.get('/api/v1/users/me/')
        assert time.time() - start < 1.0

    def test_notifications_rapide(self, auth_client):
        start = time.time()
        auth_client.get('/api/v1/notifications/')
        assert time.time() - start < 1.0

    def test_historique_paiements_rapide(self, auth_client):
        start = time.time()
        auth_client.get('/api/v1/payments/history/')
        assert time.time() - start < 1.5


class TestChargeBDD:
    """Tester les performances avec beaucoup de données"""

    def test_pagination_100_transactions(self, auth_client, client_user):
        for i in range(50):
            Transaction.objects.create(
                reference=f'IH-LOAD-{i:04d}',
                payer=client_user,
                transaction_type='visit',
                amount=5000 + i,
                platform_fee=100, net_amount=4900,
                currency='FCFA', status='completed',
                payment_method='mtn',
            )
        start = time.time()
        r = auth_client.get('/api/v1/payments/history/?page=1&page_size=20')
        duration = time.time() - start
        assert r.status_code == status.HTTP_200_OK
        assert duration < 2.0, f"Trop lent avec 50 transactions: {duration:.2f}s"

    def test_requetes_consecutives(self, api_client):
        start = time.time()
        for _ in range(10):
            api_client.get('/api/v1/properties/')
        duration = time.time() - start
        assert duration < 10.0, f"10 requêtes trop lentes: {duration:.2f}s"

    def test_recherche_avec_filtres_rapide(self, api_client, property_obj):
        start = time.time()
        api_client.get('/api/v1/properties/?city=Douala&property_type=apartment&min_price=50000&max_price=500000&has_generator=true')
        assert time.time() - start < 2.0


class TestIndex:
    """Vérifier que les index de base de données fonctionnent bien"""

    def test_recherche_par_email_indexee(self, api_client, client_user):
        start = time.time()
        for _ in range(5):
            api_client.post('/api/v1/auth/login/', {
                'email': client_user.email, 'password': 'MauvaisMDP',
            })
        assert time.time() - start < 5.0

    def test_filtre_transactions_par_user(self, auth_client, client_user):
        for i in range(20):
            Transaction.objects.create(
                reference=f'IH-IDX2-{i:03d}',
                payer=client_user,
                transaction_type='visit',
                amount=5000, platform_fee=100, net_amount=4900,
                currency='FCFA', status='completed', payment_method='mtn',
            )
        start = time.time()
        r = auth_client.get('/api/v1/payments/history/')
        assert time.time() - start < 2.0
        assert r.data['count'] >= 20
