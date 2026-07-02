from django.core.exceptions import ValidationError


ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
MAX_IMAGE_SIZE_MB   = 10


def validate_image_file(file):
    """Valide qu'un fichier uploadé est bien une image valide"""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            f"Format non supporté: {file.content_type}. Utilisez JPEG, PNG ou WebP."
        )
    max_size = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file.size > max_size:
        raise ValidationError(
            f"Image trop volumineuse ({file.size // (1024*1024)}MB). Maximum: {MAX_IMAGE_SIZE_MB}MB."
        )
    return file


ALLOWED_DOCUMENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
MAX_DOCUMENT_SIZE_MB    = 20


def validate_document_file(file):
    """Valide qu'un fichier uploadé est un document valide (PDF ou image)"""
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValidationError(
            f"Format non supporté: {file.content_type}. Utilisez PDF, JPEG ou PNG."
        )
    max_size = MAX_DOCUMENT_SIZE_MB * 1024 * 1024
    if file.size > max_size:
        raise ValidationError(
            f"Fichier trop volumineux ({file.size // (1024*1024)}MB). Maximum: {MAX_DOCUMENT_SIZE_MB}MB."
        )
    return file


import re

def validate_phone_cameroon(phone):
    """Valide un numéro de téléphone camerounais"""
    from django.core.exceptions import ValidationError
    pattern = r'^\+?237[0-9]{9}$'
    if not re.match(pattern, str(phone)):
        raise ValidationError(
            "Numéro de téléphone invalide. Format attendu: +237XXXXXXXXX"
        )
    return phone


def validate_phone_international(phone):
    """Valide un numéro de téléphone international"""
    from django.core.exceptions import ValidationError
    pattern = r'^\+[1-9][0-9]{7,14}$'
    if not re.match(pattern, str(phone)):
        raise ValidationError(
            "Numéro de téléphone invalide. Format attendu: +XXX..."
        )
    return phone
