
# INTELYA HAVEN - Exceptions personnalisées

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': _get_error_message(response.data),
                'details': response.data,
            }
        }
        response.data = error_data

    return response


def _get_error_message(data):
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        if 'non_field_errors' in data:
            return str(data['non_field_errors'][0])
        first_key = next(iter(data))
        first_value = data[first_key]
        if isinstance(first_value, list):
            return f"{first_key}: {str(first_value[0])}"
        return f"{first_key}: {str(first_value)}"
    if isinstance(data, list):
        return str(data[0])
    return str(data)


class IntelyaException(Exception):
    """Exception de base pour INTELYA HAVEN"""
    default_message = "Une erreur est survenue"
    default_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class PaymentException(IntelyaException):
    default_message = "Erreur lors du traitement du paiement"
    default_code = status.HTTP_402_PAYMENT_REQUIRED


class GPSVerificationException(IntelyaException):
    default_message = "Vous n'êtes pas à proximité du bien"
    default_code = status.HTTP_400_BAD_REQUEST


class PermissionDeniedException(IntelyaException):
    default_message = "Vous n'avez pas les permissions nécessaires"
    default_code = status.HTTP_403_FORBIDDEN


class AccountBlockedException(IntelyaException):
    default_message = "Votre compte est bloqué. Veuillez régler vos impayés."
    default_code = status.HTTP_403_FORBIDDEN
