"""
Compression automatique des images et vidéos avant stockage S3
"""
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
import logging

logger = logging.getLogger(__name__)

# Qualité de compression
IMAGE_QUALITY    = 85   # 85% qualité — bon compromis taille/qualité
MAX_IMAGE_WIDTH  = 1920 # Max 1920px de large
MAX_IMAGE_HEIGHT = 1080 # Max 1080px de haut
THUMB_SIZE       = (400, 300)


def compress_image(image_file, quality=IMAGE_QUALITY):
    """
    Compresse une image uploadée.
    Réduit la taille si trop grande, optimise la qualité.
    Retourne un nouveau fichier compressé.
    """
    try:
        img = Image.open(image_file)

        # Convertir RGBA en RGB si nécessaire (PNG avec transparence)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background

        # Redimensionner si trop grande
        if img.width > MAX_IMAGE_WIDTH or img.height > MAX_IMAGE_HEIGHT:
            img.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.LANCZOS)

        # Compresser
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)

        original_name = getattr(image_file, 'name', 'photo.jpg')
        name_without_ext = original_name.rsplit('.', 1)[0]
        compressed_name = f"{name_without_ext}.jpg"

        compressed = InMemoryUploadedFile(
            output,
            'ImageField',
            compressed_name,
            'image/jpeg',
            sys.getsizeof(output),
            None
        )

        original_size = getattr(image_file, 'size', 0)
        new_size = sys.getsizeof(output)
        if original_size > 0:
            reduction = round((1 - new_size / original_size) * 100)
            logger.info(f"[COMPRESS] {original_name}: {original_size//1024}KB → {new_size//1024}KB (-{reduction}%)")

        return compressed

    except Exception as e:
        logger.error(f"[COMPRESS] Erreur compression: {e}")
        return image_file  # Retourner l'original si échec


def create_thumbnail(image_file):
    """Crée une miniature 400x300 pour les listes"""
    try:
        img = Image.open(image_file)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        output = BytesIO()
        img.save(output, format='JPEG', quality=75, optimize=True)
        output.seek(0)
        return InMemoryUploadedFile(
            output, 'ImageField', 'thumbnail.jpg',
            'image/jpeg', sys.getsizeof(output), None
        )
    except Exception as e:
        logger.error(f"[THUMBNAIL] Erreur: {e}")
        return None
