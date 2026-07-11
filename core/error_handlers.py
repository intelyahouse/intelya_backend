"""
Handlers d'erreurs globaux — retournent toujours du JSON propre
"""
from django.http import JsonResponse


def bad_request(request, exception=None):
    return JsonResponse({
        'success': False,
        'error': {'code': 400, 'message': "Requête invalide."}
    }, status=400)


def permission_denied(request, exception=None):
    return JsonResponse({
        'success': False,
        'error': {'code': 403, 'message': "Accès refusé."}
    }, status=403)


def page_not_found(request, exception=None):
    return JsonResponse({
        'success': False,
        'error': {'code': 404, 'message': "Endpoint introuvable."}
    }, status=404)


def server_error(request):
    return JsonResponse({
        'success': False,
        'error': {'code': 500, 'message': "Erreur serveur. Notre équipe a été notifiée."}
    }, status=500)
