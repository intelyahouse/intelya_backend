from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import connection
from django.core.cache import cache
import django


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        health = {
            'status': 'healthy',
            'version': '1.0.0',
            'platform': 'INTELYA HAVEN',
        }

        # Vérifier PostgreSQL
        try:
            connection.ensure_connection()
            health['database'] = 'connected'
        except Exception:
            health['database'] = 'disconnected'
            health['status'] = 'degraded'

        # Vérifier Redis
        try:
            cache.set('health_check', 'ok', 10)
            val = cache.get('health_check')
            health['cache'] = 'connected' if val == 'ok' else 'degraded'
        except Exception:
            health['cache'] = 'disconnected'
            health['status'] = 'degraded'

        status_code = 200 if health['status'] == 'healthy' else 503
        return Response(health, status=status_code)
