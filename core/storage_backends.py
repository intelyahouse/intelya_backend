"""
INTELYA HAVEN — Backends de stockage S3
Séparation stricte fichiers publics (photos biens) vs privés (CNI, documents)
"""
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class PublicMediaStorage(S3Boto3Storage):
    """
    Stockage pour les médias publics : photos de biens, avatars.
    URLs directes sans signature — accessible par tout le monde.
    """
    location = 'media/public'
    default_acl = 'public-read'
    querystring_auth = False
    file_overwrite = False


class PrivateMediaStorage(S3Boto3Storage):
    """
    Stockage pour les médias privés : CNI, documents légaux, selfies.
    URLs signées qui expirent après 1 heure.
    Seuls les utilisateurs authentifiés et autorisés peuvent accéder.
    """
    location = 'media/private'
    default_acl = 'private'
    querystring_auth = True
    file_overwrite = False
    custom_domain = False

    def get_presigned_url(self, name, expiry=3600):
        """Génère une URL signée avec expiration personnalisée."""
        return self.bucket.meta.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket.name, 'Key': self._normalize_name(name)},
            ExpiresIn=expiry,
        )
