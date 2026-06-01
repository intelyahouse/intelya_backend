from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import connection
from django.core.cache import cache
import time


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        health = {
            'status': 'ok',
            'timestamp': time.time(),
            'services': {}
        }

        # Vérifier PostgreSQL
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health['services']['database'] = 'ok'
        except Exception as e:
            health['services']['database'] = f'error: {str(e)}'
            health['status'] = 'degraded'

        # Vérifier Redis
        try:
            cache.set('health_check', '1', 5)
            val = cache.get('health_check')
            health['services']['redis'] = 'ok' if val else 'error'
        except Exception as e:
            health['services']['redis'] = f'error: {str(e)}'
            health['status'] = 'degraded'

        return Response(health)
