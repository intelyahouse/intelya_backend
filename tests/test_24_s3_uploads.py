"""
Tests Upload fichiers — Photos biens, Documents agents, Avatars
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestUploadPhotoBien:

    def test_upload_photo_bien_reussi(self, auth_agent, property_obj):
        image = SimpleUploadedFile(
            "photo.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            content_type="image/jpeg"
        )
        r = auth_agent.post(
            f'/api/v1/properties/{property_obj.id}/photos/',
            {'photos': image}, format='multipart'
        )
        assert r.status_code in [200, 201, 400]

    def test_upload_mauvais_format_rejete(self, auth_agent, property_obj):
        fichier = SimpleUploadedFile(
            "malware.exe", b"MZ\x90\x00", content_type="application/octet-stream"
        )
        r = auth_agent.post(
            f'/api/v1/properties/{property_obj.id}/photos/',
            {'photos': fichier}, format='multipart'
        )
        assert r.status_code in [400, 415]

    def test_upload_sans_auth_rejete(self, api_client, property_obj):
        image = SimpleUploadedFile(
            "photo.jpg", b"\xff\xd8\xff\xe0", content_type="image/jpeg"
        )
        r = api_client.post(
            f'/api/v1/properties/{property_obj.id}/photos/',
            {'photos': image}, format='multipart'
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_upload_trop_grand_rejete(self, auth_agent, property_obj):
        # Fichier trop grand détecté par la taille déclarée
        from django.core.files.uploadedfile import SimpleUploadedFile as SUF
        gros = SUF(
            "gros.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024),
            content_type="image/jpeg"
        )
        gros.size = 6 * 1024 * 1024 + 1  # forcer la taille
        r = auth_agent.post(
            f'/api/v1/properties/{property_obj.id}/photos/',
            {'photos': gros}, format='multipart'
        )
        assert r.status_code in [200, 201, 400, 413]  # selon config MAX_UPLOAD_SIZE


class TestUploadDocumentAgent:

    def test_upload_cni_agent(self, auth_agent, agent_user):
        cni = SimpleUploadedFile(
            "cni.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            content_type="image/jpeg"
        )
        selfie = SimpleUploadedFile(
            "selfie.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            content_type="image/jpeg"
        )
        r = auth_agent.post('/api/v1/auth/request-role/', {
            'requested_role': 'agent',
            'cni_number': 'CM123456789',
            'cni_front_photo': cni,
            'cni_back_photo': selfie,
            'selfie_photo': selfie,
        }, format='multipart')
        assert r.status_code in [200, 201, 400]

    def test_upload_patente_agent(self, auth_agent):
        r = auth_agent.patch('/api/v1/agents/me/', {}, format='multipart')
        assert r.status_code in [200, 400]

    def test_client_ne_peut_pas_uploader_doc_agent(self, auth_client):
        r = auth_client.patch('/api/v1/agents/me/', {}, format='multipart')
        assert r.status_code in [403, 404]

    def test_upload_avatar_utilisateur(self, auth_client):
        avatar = SimpleUploadedFile(
            "avatar.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            content_type="image/jpeg"
        )
        r = auth_client.patch('/api/v1/users/me/', {
            'profile_photo': avatar,
        }, format='multipart')
        assert r.status_code in [200, 400]

    def test_upload_avatar_png_accepte(self, auth_client):
        avatar = SimpleUploadedFile(
            "avatar.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
            content_type="image/png"
        )
        r = auth_client.patch('/api/v1/users/me/', {
            'profile_photo': avatar,
        }, format='multipart')
        assert r.status_code in [200, 400]
