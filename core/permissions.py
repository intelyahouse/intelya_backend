# INTELYA HAVEN - Permissions par rôle

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Reservé à l administrateur de la plateforme"""
    message = "Acces reserve aux administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "admin" and
            not request.user.is_blocked
        )


class IsAgent(BasePermission):
    """Reservé aux agents immobiliers valides et non bloques"""
    message = "Acces reserve aux agents immobiliers."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "agent" and
            request.user.is_validated and
            not request.user.is_blocked
        )


class IsOwner(BasePermission):
    """Reservé aux proprietaires valides et non bloques"""
    message = "Acces reserve aux proprietaires."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "owner" and
            request.user.is_validated and
            not request.user.is_blocked
        )


class IsClient(BasePermission):
    """Reservé aux clients non bloques"""
    message = "Acces reserve aux clients."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ["client", "tenant"] and
            not request.user.is_blocked
        )


class IsTenant(BasePermission):
    """Reservé aux locataires actifs non bloques"""
    message = "Acces reserve aux locataires."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "tenant" and
            not request.user.is_blocked
        )


class IsAgentOrAdmin(BasePermission):
    """Agents ou administrateurs non bloques"""
    message = "Acces reserve aux agents ou administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ["agent", "admin"] and
            not request.user.is_blocked
        )


class IsOwnerOrAgent(BasePermission):
    """Proprietaires ou agents non bloques"""
    message = "Acces reserve aux proprietaires ou agents."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ["owner", "agent", "admin"] and
            not request.user.is_blocked
        )


class IsAccountNotBlocked(BasePermission):
    """Verifie que le compte n est pas bloque"""
    message = "Votre compte est bloque. Veuillez regler vos impayes."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            not request.user.is_blocked
        )


class IsAdminOrReadOnly(BasePermission):
    """Admin peut tout faire, les autres peuvent seulement lire"""
    message = "Modification reservee aux administrateurs."

    def has_permission(self, request, view):
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "admin"
        )

class IsPhoneVerified(BasePermission):
    """Exige un telephone verifie - a utiliser sur les actions sensibles
    (contacter un agent, reserver une visite, envoyer un message, signer un contrat)"""
    message = "Merci de verifier votre numero de telephone avant de continuer."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_phone_verified
        )

