from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Gestionnaire d'erreurs unifié INTELYA HAVEN.
    Retourne toujours le même format JSON propre.
    Ne révèle jamais les détails internes en production.
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            'success': False,
            'error': {
                'code':    response.status_code,
                'message': _get_clean_message(response.data, response.status_code),
            }
        }
        # En développement on ajoute les détails
        from django.conf import settings
        if settings.DEBUG:
            error_data['error']['details'] = response.data

        response.data = error_data
        return response

    # Erreur non gérée par DRF (500)
    logger.error(f"Erreur non gérée: {exc}", exc_info=True)
    return Response({
        'success': False,
        'error': {
            'code':    500,
            'message': "Une erreur interne est survenue. Notre équipe a été notifiée.",
        }
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_clean_message(data, status_code):
    """Retourne un message propre sans révéler les internals"""
    MESSAGES = {
        400: "Données invalides. Vérifiez les informations soumises.",
        401: "Authentification requise.",
        403: "Accès refusé.",
        404: "Ressource introuvable.",
        405: "Méthode non autorisée.",
        429: "Trop de requêtes. Veuillez patienter.",
        500: "Erreur serveur interne.",
    }

    # Essayer d'extraire un message utile sans révéler les internals
    if isinstance(data, dict):
        if 'detail' in data:
            msg = str(data['detail'])
            # Ne pas révéler les noms de tables/modèles
            if 'DoesNotExist' in msg or 'matching query' in msg:
                return MESSAGES.get(404, "Ressource introuvable.")
            return msg

        if 'non_field_errors' in data:
            return str(data['non_field_errors'][0])

        # Erreur de validation — retourner le premier champ
        for field, errors in data.items():
            if isinstance(errors, list) and errors:
                return f"{field}: {errors[0]}"

    if isinstance(data, list) and data:
        return str(data[0])

    return MESSAGES.get(status_code, "Une erreur est survenue.")
