"""
Middlewares de sécurité INTELYA HAVEN
"""
import logging
import time
import bleach
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Ajoute les headers de sécurité sur toutes les réponses"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Headers de sécurité
        response['X-Content-Type-Options']   = 'nosniff'
        response['X-Frame-Options']           = 'DENY'
        response['X-XSS-Protection']          = '1; mode=block'
        response['Referrer-Policy']           = 'strict-origin-when-cross-origin'
        response['Permissions-Policy']        = 'geolocation=(), microphone=(), camera=()'
        response['Cache-Control']             = 'no-store'
        response['Pragma']                    = 'no-cache'

        # Supprimer les headers qui révèlent la stack
        if 'X-Powered-By' in response:
            del response['X-Powered-By']
        if 'Server' in response:
            del response['Server']

        return response


class RequestLoggingMiddleware:
    """Log les requêtes sensibles pour audit"""

    SENSITIVE_PATHS = [
        '/api/v1/auth/login/',
        '/api/v1/auth/register/',
        '/api/v1/payments/',
        '/api/v1/admin-panel/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response   = self.get_response(request)
        duration   = time.time() - start_time

        # Log les requêtes sur les endpoints sensibles
        if any(request.path.startswith(p) for p in self.SENSITIVE_PATHS):
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if isinstance(ip, str):
                ip = ip.split(',')[0].strip()

            logger.info(
                f"[REQUEST] {request.method} {request.path} "
                f"| IP: {ip} "
                f"| Status: {response.status_code} "
                f"| Duration: {duration:.3f}s "
                f"| User: {getattr(request, 'user', 'anon')}"
            )

        # Alerter si requête lente (> 3 secondes)
        if duration > 3:
            logger.warning(f"[SLOW REQUEST] {request.method} {request.path} took {duration:.3f}s")

        return response


class BlockSuspiciousRequestsMiddleware:
    """Bloque les requêtes suspectes (attaques communes)"""

    BLOCKED_PATTERNS = [
        '../', '..\\',           # Path traversal
        '<script',               # XSS
        'UNION SELECT',          # SQL Injection
        'DROP TABLE',            # SQL Injection
        '/etc/passwd',           # LFI
        'eval(',                 # Code injection
        'base64_decode',         # Code injection
        'phpinfo()',             # PHP probing
        '.php',                  # PHP files
        '.asp',                  # ASP files
        'wp-admin',              # WordPress scanning
        'xmlrpc',                # WordPress attack
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path      = request.path.lower()
        query     = request.META.get('QUERY_STRING', '').lower()
        full_path = f"{path}?{query}"

        for pattern in self.BLOCKED_PATTERNS:
            if pattern.lower() in full_path:
                ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
                logger.warning(f"[BLOCKED] Suspicious request from {ip}: {request.path}")
                return JsonResponse(
                    {'error': 'Requête non autorisée'},
                    status=400
                )

        return self.get_response(request)
