import pytest
import time
from unittest.mock import patch
from rest_framework import status
from apps.payments.models import Transaction

pytestmark = pytest.mark.django_db


class TestNotifications:

    def test_voir_notifications(self, auth_client):
        r = auth_client.get('/api/v1/notifications/')
        assert r.status_code == status.HTTP_200_OK

    def test_marquer_lues(self, auth_client):
        r = auth_client.post('/api/v1/notifications/mark-read/')
        assert r.status_code in [200, 201]

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/notifications/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestReferrals:

    def test_voir_filleuls(self, auth_client):
        r = auth_client.get('/api/v1/referrals/mine/')
        assert r.status_code == status.HTTP_200_OK

    def test_codes_uniques(self, client_user, create_user):
        autre = create_user(email='ref2@test.cm', phone='+237670000070', role='client')
        assert client_user.referral_code != autre.referral_code
        assert client_user.referral_code is not None

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/referrals/mine/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestBoost:

    def test_prix_boost(self, auth_client):
        r = auth_client.get('/api/v1/boost/prices/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_voit_ses_boosts(self, auth_agent):
        r = auth_agent.get('/api/v1/boost/mine/')
        assert r.status_code == status.HTTP_200_OK

    def test_agent_achete_boost(self, auth_agent):
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

    def test_client_ne_peut_pas_booster(self, auth_client):
        r = auth_client.post('/api/v1/boost/activate/', {
            'level': 'bronze', 'duration_days': 7, 'target_city': 'Douala',
        })
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestLitiges:

    def test_creer_signalement(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'harassment',
            'description': 'Cet agent me harcèle.',
        })
        assert r.status_code in [200, 201]

    def test_creer_litige(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'agent',
            'title': 'Problème avec agent',
            'description': 'Description du litige entre les deux parties concernées',
        })
        assert r.status_code in [200, 201]

    def test_voir_mes_litiges(self, auth_client):
        r = auth_client.get('/api/v1/disputes/disputes/')
        assert r.status_code == status.HTTP_200_OK

    def test_admin_voit_litiges(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/disputes/')
        assert r.status_code == status.HTTP_200_OK

    def test_admin_voit_signalements(self, auth_admin):
        r = auth_admin.get('/api/v1/admin-panel/reports/')
        assert r.status_code == status.HTTP_200_OK


class TestContrats:

    def test_voir_mes_baux(self, auth_agent):
        r = auth_agent.get('/api/v1/contracts/leases/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_paiements_loyer(self, auth_client):
        r = auth_client.get('/api/v1/leases/payments/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_mes_plaintes(self, auth_client):
        r = auth_client.get('/api/v1/leases/complaints/')
        assert r.status_code == status.HTTP_200_OK


class TestAvis:

    def test_voir_avis_bien(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/reviews/property/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_voir_avis_agent(self, api_client, agent_user):
        r = api_client.get(f'/api/v1/reviews/agent/{agent_user.id}/')
        assert r.status_code == status.HTTP_200_OK


class TestHealthEtPerformance:

    def test_health_check(self, api_client):
        r = api_client.get('/api/health/')
        assert r.status_code == status.HTTP_200_OK

    def test_swagger_accessible(self, api_client):
        r = api_client.get('/api/docs/')
        assert r.status_code == status.HTTP_200_OK

    def test_api_rapide(self, api_client):
        start = time.time()
        api_client.get('/api/v1/properties/')
        assert time.time() - start < 2.0

    def test_5_requetes_rapides(self, api_client):
        start = time.time()
        for _ in range(5):
            api_client.get('/api/v1/properties/')
        assert time.time() - start < 5.0

    def test_transactions_indexees(self, auth_client, client_user):
        for i in range(10):
            Transaction.objects.create(
                reference=f'IH-IDX-{i:03d}', payer=client_user,
                transaction_type='visit', amount=5000,
                platform_fee=100, net_amount=4900,
                currency='FCFA', status='completed', payment_method='mtn',
            )
        start = time.time()
        auth_client.get('/api/v1/payments/history/')
        assert time.time() - start < 2.0


class TestConfiguration:

    def test_secret_key_securisee(self):
        import django.conf
        s = django.conf.settings
        assert s.SECRET_KEY not in ['', 'changeme', 'django-insecure-']
        assert len(s.SECRET_KEY) >= 40

    def test_kpay_configure(self):
        import django.conf
        s = django.conf.settings
        assert hasattr(s, 'KPAY_API_KEY')
        assert hasattr(s, 'KPAY_RETAILER_ID')

    def test_db_postgis(self):
        import django.conf
        s = django.conf.settings
        assert 'postgis' in s.DATABASES['default']['ENGINE']

    def test_redis_configure(self):
        import django.conf
        s = django.conf.settings
        assert 'redis' in s.CACHES['default']['BACKEND'].lower()

    def test_celery_configure(self):
        import django.conf
        s = django.conf.settings
        assert hasattr(s, 'CELERY_BROKER_URL')
        assert hasattr(s, 'CELERY_BEAT_SCHEDULE')

    def test_s3_configure(self):
        import django.conf
        s = django.conf.settings
        assert hasattr(s, 'AWS_STORAGE_BUCKET_NAME')

    def test_firebase_configure(self):
        import django.conf
        s = django.conf.settings
        assert hasattr(s, 'FIREBASE_CREDENTIALS_PATH')

    def test_timezone_douala(self):
        import django.conf
        s = django.conf.settings
        assert s.CELERY_TIMEZONE == 'Africa/Douala'

    def test_jwt_configure(self):
        import django.conf
        s = django.conf.settings
        assert hasattr(s, 'SIMPLE_JWT')
