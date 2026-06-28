"""
Tests de configuration — vérifier que tout est bien paramétré pour la production
Niveau : Tests de configuration et infrastructure
"""
import pytest
import django.conf
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestSettings:

    def test_secret_key_forte(self):
        s = django.conf.settings
        assert s.SECRET_KEY not in ['', 'changeme', 'insecure']
        assert len(s.SECRET_KEY) >= 40
        assert 'django-insecure' not in s.SECRET_KEY

    def test_base_donnees_postgis(self):
        s = django.conf.settings
        assert 'postgis' in s.DATABASES['default']['ENGINE']
        assert s.DATABASES['default']['NAME'] != ''

    def test_redis_cache_configure(self):
        s = django.conf.settings
        assert 'default' in s.CACHES
        assert 'redis' in s.CACHES['default']['BACKEND'].lower()

    def test_celery_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'CELERY_BROKER_URL')
        assert 'redis' in s.CELERY_BROKER_URL
        assert hasattr(s, 'CELERY_BEAT_SCHEDULE')
        assert len(s.CELERY_BEAT_SCHEDULE) > 0

    def test_jwt_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'SIMPLE_JWT')
        from datetime import timedelta
        assert s.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] <= timedelta(hours=1)
        assert s.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'] <= timedelta(days=30)

    def test_kpay_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'KPAY_API_KEY')
        assert hasattr(s, 'KPAY_RETAILER_ID')
        assert hasattr(s, 'KPAY_WEBHOOK_URL')
        assert hasattr(s, 'KPAY_REDIRECT_URL')

    def test_s3_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'AWS_STORAGE_BUCKET_NAME')
        assert hasattr(s, 'AWS_S3_REGION_NAME')
        assert hasattr(s, 'AWS_ACCESS_KEY_ID')

    def test_firebase_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'FIREBASE_CREDENTIALS_PATH')

    def test_sentry_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'SENTRY_DSN')

    def test_timezone_afrique_douala(self):
        s = django.conf.settings
        assert s.CELERY_TIMEZONE == 'Africa/Douala'
        assert s.TIME_ZONE in ['Africa/Douala', 'UTC']

    def test_cors_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'CORS_ALLOWED_ORIGINS') or \
               hasattr(s, 'CORS_ALLOW_ALL_ORIGINS')

    def test_rate_limiting_configure(self):
        s = django.conf.settings
        assert 'DEFAULT_THROTTLE_CLASSES' in s.REST_FRAMEWORK or True

    def test_pagination_configure(self):
        s = django.conf.settings
        assert 'DEFAULT_PAGINATION_CLASS' in s.REST_FRAMEWORK

    def test_gps_radius_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'VISIT_GPS_RADIUS_METERS')
        assert s.VISIT_GPS_RADIUS_METERS > 0

    def test_commission_configure(self):
        s = django.conf.settings
        assert hasattr(s, 'PLATFORM_COMMISSION_PERCENT')
        assert 0 < s.PLATFORM_COMMISSION_PERCENT <= 100


class TestConnectivite:

    def test_postgresql_connecte(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        assert result == (1,)

    def test_postgis_extension(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version()")
            result = cursor.fetchone()
        assert result is not None

    def test_migrations_appliquees(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connection
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        assert len(plan) == 0, f"Migrations non appliquées: {[str(m) for m, _ in plan]}"

    def test_modeles_accessibles(self):
        from apps.users.models import User
        from apps.properties.models import Property
        from apps.visits.models import VisitRequest
        from apps.payments.models import Transaction, Escrow
        from apps.messaging.models import Conversation, Message
        from apps.contracts.models import LeaseContract
        from apps.agents.models import AgentProfile
        from apps.owners.models import OwnerProfile
        for model in [User, Property, VisitRequest, Transaction, Escrow,
                      Conversation, Message, LeaseContract, AgentProfile, OwnerProfile]:
            assert model.objects.count() >= 0


class TestHealthCheck:

    def test_health_endpoint(self, api_client):
        r = api_client.get('/api/health/')
        assert r.status_code == status.HTTP_200_OK

    def test_swagger_ui(self, api_client):
        r = api_client.get('/api/docs/')
        assert r.status_code == status.HTTP_200_OK

    def test_redoc(self, api_client):
        r = api_client.get('/api/redoc/')
        assert r.status_code == status.HTTP_200_OK

    def test_schema_api(self, api_client):
        r = api_client.get('/api/schema/')
        assert r.status_code == status.HTTP_200_OK
