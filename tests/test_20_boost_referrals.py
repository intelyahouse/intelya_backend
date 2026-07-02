"""
Tests Boost et Parrainage
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from unittest.mock import patch
from apps.boost.models import Boost
from apps.referrals.models import Referral

pytestmark = pytest.mark.django_db


class TestBoostComplet:

    def test_voir_prix_boost_authentifie(self, auth_client):
        """BoostPricesView requiert authentification"""
        r = auth_client.get('/api/v1/boost/prices/')
        assert r.status_code == status.HTTP_200_OK

    def test_boost_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/boost/prices/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_prix_bronze_7_jours(self):
        assert Boost.get_price('bronze', 7) == 5000

    def test_prix_silver_7_jours(self):
        assert Boost.get_price('silver', 7) == 10000

    def test_prix_gold_7_jours(self):
        assert Boost.get_price('gold', 7) == 20000

    def test_prix_bronze_30_jours(self):
        assert Boost.get_price('bronze', 30) == 18000

    def test_prix_silver_30_jours(self):
        assert Boost.get_price('silver', 30) == 35000

    def test_prix_gold_30_jours(self):
        assert Boost.get_price('gold', 30) == 65000

    def test_agent_voit_ses_boosts(self, auth_agent):
        r = auth_agent.get('/api/v1/boost/mine/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_achete_boost_bronze(self, auth_agent):
        mock = {'success': True, 'reference': 'KPAY-B001', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
            r = auth_agent.post('/api/v1/boost/activate/', {
                'level': 'bronze',
                'duration_days': 7,
                'target_city': 'Douala',
                'payment_method': 'mtn',
                'phone_number': '+237670000002',
            })
        assert r.status_code in [200, 201]

    def test_agent_achete_boost_gold(self, auth_agent):
        mock = {'success': True, 'reference': 'KPAY-G001', 'status': 'pending', 'ussd_code': '', 'checkout_url': ''}
        with patch('apps.payments.services.kpay.kpay_service.collect', return_value=mock):
            r = auth_agent.post('/api/v1/boost/activate/', {
                'level': 'gold',
                'duration_days': 30,
                'target_city': 'Yaoundé',
                'payment_method': 'orange',
                'phone_number': '+237690000002',
            })
        assert r.status_code in [200, 201]

    def test_client_ne_peut_pas_booster(self, auth_client):
        r = auth_client.post('/api/v1/boost/activate/', {
            'level': 'bronze', 'duration_days': 7, 'target_city': 'Douala',
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_ne_peut_pas_booster(self, auth_owner):
        r = auth_owner.post('/api/v1/boost/activate/', {
            'level': 'bronze', 'duration_days': 7, 'target_city': 'Douala',
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_boost_expire_detecte(self, agent_user):
        boost = Boost.objects.create(
            agent=agent_user, level='bronze', duration_days=7,
            target_city='Douala', price_paid=5000, is_active=True,
            start_date=timezone.now() - timedelta(days=8),
            end_date=timezone.now() - timedelta(days=1),
        )
        assert boost.is_expired() is True

    def test_boost_actif_non_expire(self, agent_user):
        boost = Boost.objects.create(
            agent=agent_user, level='gold', duration_days=30,
            target_city='Yaoundé', price_paid=65000, is_active=True,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
        )
        assert boost.is_expired() is False

    def test_admin_voit_tous_boosts(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/boosts/')
        assert r.status_code == status.HTTP_200_OK


class TestParrainage:

    def test_voir_mes_filleuls(self, auth_client):
        r = auth_client.get('/api/v1/referrals/mine/')
        assert r.status_code == status.HTTP_200_OK

    def test_referral_codes_uniques(self, client_user, create_user):
        u2 = create_user(email='ref_u2@test.cm', phone='+237670000070', role='client')
        u3 = create_user(email='ref_u3@test.cm', phone='+237670000071', role='client')
        codes = {client_user.referral_code, u2.referral_code, u3.referral_code}
        assert len(codes) == 3
        for code in codes:
            assert code is not None
            assert len(code) >= 6

    def test_inscription_avec_code(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Filleul', 'last_name': 'Test',
            'email': 'filleul@test.cm', 'phone': '+237670000072',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'referral_code': client_user.referral_code,
        })
        assert r.status_code == status.HTTP_201_CREATED

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/referrals/mine/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
