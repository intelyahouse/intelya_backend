from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from .models import OwnerProfile, BankAccount, PaymentPreferences
from .serializers import (
    OwnerProfileSerializer, OwnerBankAccountSerializer,
    BankAccountSerializer, PaymentPreferencesSerializer
)
from apps.agents.models import OwnerAgentRelation, AgentProfile
from core.permissions import IsOwner, IsAdmin
from core.utils import success_response, error_response
from django.utils import timezone

User = get_user_model()


class OwnerProfileView(APIView):
    """Mon profil propriétaire"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners'], summary="Mon profil propriétaire")
    def get(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil propriétaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(success_response(OwnerProfileSerializer(profile).data))

    @extend_schema(tags=['Owners'], summary="Modifier mon profil")
    def patch(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = OwnerProfileSerializer(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(success_response(serializer.data, "Profil mis à jour"))


class OwnerBankAccountView(APIView):
    """Gérer les comptes bancaires du propriétaire"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners'], summary="Mettre à jour mes comptes bancaires")
    def patch(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = OwnerBankAccountSerializer(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(success_response(serializer.data, "Comptes bancaires mis à jour"))


class BankAccountListCreateView(APIView):
    """CRUD : Lister et créer des comptes bancaires"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners - Bank'], summary="Lister mes comptes bancaires")
    def get(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil propriétaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        accounts = BankAccount.objects.filter(owner=profile, is_active=True)
        serializer = BankAccountSerializer(accounts, many=True)
        return Response(success_response(serializer.data))

    @extend_schema(tags=['Owners - Bank'], summary="Ajouter un compte bancaire")
    def post(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil propriétaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BankAccountSerializer(
            data=request.data,
            context={'owner': profile}
        )
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return Response(
            success_response(serializer.data, "Compte bancaire ajouté avec succès"),
            status=status.HTTP_201_CREATED
        )


class BankAccountDetailView(APIView):
    """CRUD : Détail, mise à jour et suppression d'un compte bancaire"""
    permission_classes = [IsAuthenticated, IsOwner]

    def _get_account(self, request, account_id):
        """Helper pour récupérer un compte et vérifier que c'est celui de l'utilisateur"""
        try:
            profile = OwnerProfile.objects.get(user=request.user)
            account = BankAccount.objects.get(id=account_id, owner=profile)
            return profile, account
        except OwnerProfile.DoesNotExist:
            return None, None
        except BankAccount.DoesNotExist:
            return None, None

    @extend_schema(tags=['Owners - Bank'], summary="Détails d'un compte bancaire")
    def get(self, request, account_id):
        profile, account = self._get_account(request, account_id)
        if not account:
            return Response(
                error_response("Compte bancaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BankAccountSerializer(account)
        return Response(success_response(serializer.data))

    @extend_schema(tags=['Owners - Bank'], summary="Mettre à jour un compte bancaire")
    def patch(self, request, account_id):
        profile, account = self._get_account(request, account_id)
        if not account:
            return Response(
                error_response("Compte bancaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BankAccountSerializer(
            account,
            data=request.data,
            partial=True,
            context={'owner': profile}
        )
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return Response(success_response(serializer.data, "Compte bancaire mis à jour"))

    @extend_schema(tags=['Owners - Bank'], summary="Supprimer un compte bancaire")
    def delete(self, request, account_id):
        profile, account = self._get_account(request, account_id)
        if not account:
            return Response(
                error_response("Compte bancaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Vérifier que ce n'est pas le compte par défaut
        if account.is_default:
            return Response(
                error_response(
                    "Impossible de supprimer le compte par défaut. "
                    "Définissez d'abord un autre compte comme par défaut."
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        account.is_active = False
        account.save()
        
        return Response(success_response(message="Compte bancaire supprimé"))


class BankAccountSetDefaultView(APIView):
    """Définir un compte bancaire comme par défaut"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners - Bank'], summary="Définir un compte comme par défaut")
    def post(self, request, account_id):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
            account = BankAccount.objects.get(id=account_id, owner=profile)
        except (OwnerProfile.DoesNotExist, BankAccount.DoesNotExist):
            return Response(
                error_response("Compte bancaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        account.is_default = True
        account.save()
        
        serializer = BankAccountSerializer(account)
        return Response(success_response(
            serializer.data,
            "Compte défini comme par défaut"
        ))


class PaymentPreferencesView(APIView):
    """CRUD pour les préférences de paiement"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners - Bank'], summary="Mes préférences de payout")
    def get(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
            prefs = PaymentPreferences.objects.get(owner=profile)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil propriétaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        except PaymentPreferences.DoesNotExist:
            # Créer les préférences par défaut si elles n'existent pas
            prefs = PaymentPreferences.objects.create(owner=profile)
        
        serializer = PaymentPreferencesSerializer(prefs)
        return Response(success_response(serializer.data))

    @extend_schema(tags=['Owners - Bank'], summary="Mettre à jour mes préférences de payout")
    def patch(self, request):
        try:
            profile = OwnerProfile.objects.get(user=request.user)
        except OwnerProfile.DoesNotExist:
            return Response(
                error_response("Profil propriétaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            prefs = PaymentPreferences.objects.get(owner=profile)
        except PaymentPreferences.DoesNotExist:
            prefs = PaymentPreferences.objects.create(owner=profile)
        
        serializer = PaymentPreferencesSerializer(
            prefs,
            data=request.data,
            partial=True,
            context={'owner': profile}
        )
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return Response(success_response(
            serializer.data,
            "Préférences de payout mises à jour"
        ))


class OwnerAgentRelationView(APIView):
    """Gérer la relation propriétaire-agent"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners'], summary="Mon agent actuel")
    def get(self, request):
        relation = OwnerAgentRelation.objects.filter(
            owner=request.user, status='active'
        ).select_related('agent').first()

        if not relation:
            return Response(success_response(
                {'agent': None},
                "Vous n'avez pas d'agent actif"
            ))

        return Response(success_response({
            'relation_id': str(relation.id),
            'agent_id': str(relation.agent.id),
            'agent_name': relation.agent.get_full_name(),
            'agent_phone': relation.agent.phone,
            'contract_start': relation.contract_start,
            'contract_end': relation.contract_end,
            'status': relation.status,
        }))

    @extend_schema(tags=['Owners'], summary="Choisir un agent")
    def post(self, request):
        # Vérifier si déjà un agent actif
        if OwnerAgentRelation.objects.filter(owner=request.user, status='active').exists():
            return Response(
                error_response("Vous avez déjà un agent actif. Résiliez d'abord le contrat actuel."),
                status=status.HTTP_400_BAD_REQUEST
            )

        agent_id = request.data.get('agent_id')
        contract_end = request.data.get('contract_end')

        try:
            agent_profile = AgentProfile.objects.get(id=agent_id, user__is_validated=True)
        except AgentProfile.DoesNotExist:
            return Response(
                error_response("Agent introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )

        relation = OwnerAgentRelation.objects.create(
            owner=request.user,
            agent=agent_profile.user,
            status='active',
            contract_start=timezone.now().date(),
            contract_end=contract_end if contract_end else None,
        )

        return Response(success_response(
            {'relation_id': str(relation.id)},
            f"Vous êtes maintenant lié à l'agent {agent_profile.user.get_full_name()}"
        ), status=status.HTTP_201_CREATED)

    @extend_schema(tags=['Owners'], summary="Résilier le contrat avec mon agent")
    def delete(self, request):
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                error_response("Un motif de résiliation est obligatoire"),
                status=status.HTTP_400_BAD_REQUEST
            )

        relation = OwnerAgentRelation.objects.filter(
            owner=request.user, status='active'
        ).first()

        if not relation:
            return Response(
                error_response("Aucun contrat actif trouvé"),
                status=status.HTTP_404_NOT_FOUND
            )

        relation.status = 'terminated'
        relation.termination_reason = reason
        relation.terminated_at = timezone.now()
        relation.terminated_by = request.user
        relation.save()

        return Response(success_response(
            message="Contrat résilié. Préavis de 30 jours en cours."
        ))
