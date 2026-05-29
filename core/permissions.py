# ===================================
# INTELYA HAVEN - Permissions par rôle
# ===================================

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Réservé à l'administrateur de la plateforme"""
    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsAgent(BasePermission):
    """Réservé aux agents immobiliers validés"""
    message = "Accès réservé aux agents immobiliers."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'agent' and
            request.user.is_validated
        )


class IsOwner(BasePermission):
    """Réservé aux propriétaires validés"""
    message = "Accès réservé aux propriétaires."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'owner' and
            request.user.is_validated
        )


class IsClient(BasePermission):
    """Réservé aux clients"""
    message = "Accès réservé aux clients."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['client', 'tenant']
        )


class IsTenant(BasePermission):
    """Réservé aux locataires actifs"""
    message = "Accès réservé aux locataires."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'tenant'
        )


class IsAgentOrAdmin(BasePermission):
    """Agents ou administrateurs"""
    message = "Accès réservé aux agents ou administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['agent', 'admin']
        )


class IsOwnerOrAgent(BasePermission):
    """Propriétaires ou agents"""
    message = "Accès réservé aux propriétaires ou agents."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['owner', 'agent', 'admin']
        )


class IsAccountNotBlocked(BasePermission):
    """Vérifie que le compte n'est pas bloqué"""
    message = "Votre compte est bloqué. Veuillez régler vos impayés."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            not request.user.is_blocked
        )
