from django.core.exceptions import ValidationError
import os


ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi']

MAX_IMAGE_SIZE   = 5 * 1024 * 1024   # 5 MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE   = 100 * 1024 * 1024  # 100 MB


def validate_image_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Format non autorisé. Utilisez: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError(f"Fichier trop volumineux. Maximum: 5 MB")


def validate_document_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(f"Format non autorisé. Utilisez: {', '.join(ALLOWED_DOCUMENT_EXTENSIONS)}")
    if file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError(f"Fichier trop volumineux. Maximum: 10 MB")


def validate_video_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(f"Format non autorisé. Utilisez: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}")
    if file.size > MAX_VIDEO_SIZE:
        raise ValidationError(f"Vidéo trop volumineuse. Maximum: 100 MB")


def validate_phone_cameroon(value):
    """Valide le format téléphone camerounais +237XXXXXXXXX"""
    import re
    pattern = r'^\+237[6-9][0-9]{8}$'
    if not re.match(pattern, value):
        raise ValidationError(
            "Format téléphone invalide. Utilisez le format +237XXXXXXXXX (ex: +237670000000)"
        )
