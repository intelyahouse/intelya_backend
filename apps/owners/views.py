from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from .models import OwnerProfile
from .serializers import OwnerProfileSerializer, OwnerBankAccountSerializer
from apps.agents.models import OwnerAgentRelation, AgentProfile
from core.permissions import IsOwner, IsOwnerRole, IsAdmin
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


class OwnerAgentRelationView(APIView):
    """Gérer la relation propriétaire-agent"""
    permission_classes = [IsAuthenticated, IsOwner]

    @extend_schema(tags=['Owners'], summary="Mon agent actuel")
    def get(self, request):
        relation = OwnerAgentRelation.objects.filter(
            owner=request.user, status='active'
        ).select_related('agent', 'agency').first()

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
            'agency_id': str(relation.agency_id),
            'agency_name': relation.agency.name,
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
            agency=agent_profile.agency,
            status='active',
            contract_start=timezone.now().date(),
            contract_end=contract_end if contract_end else None,
        )

        return Response(success_response(
            {'relation_id': str(relation.id), 'agency_id': str(agent_profile.agency_id)},
            f"Vous êtes maintenant lié à l'agent {agent_profile.user.get_full_name()} ({agent_profile.agency.name})"
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


class OwnerDashboardView(APIView):
    """Tableau de bord proprietaire — statut et actions disponibles.
    Accessible meme non valide (IsOwnerRole, pas IsOwner) : c'est justement
    ici qu'un proprietaire en attente doit voir qu'il est en attente."""
    permission_classes = [IsAuthenticated, IsOwnerRole]

    @extend_schema(tags=['Owners'], summary="Mon tableau de bord propriétaire")
    def get(self, request):
        from apps.properties.models import Property
        user = request.user
        profile = OwnerProfile.objects.filter(user=user).first()

        properties = Property.objects.filter(owner=user)
        total_properties = properties.count()

        relation = OwnerAgentRelation.objects.filter(
            owner=user, status='active'
        ).select_related('agent__agent_profile__agency').first()
        agency = None
        if relation and hasattr(relation.agent, 'agent_profile'):
            agency = relation.agent.agent_profile.agency

        status_data = {
            'is_validated': user.is_validated,
            'total_properties': total_properties,
            'available_properties': properties.filter(status='available').count(),
            'rented_properties': properties.filter(status='rented').count(),
            'manages_own_tenants': profile.manages_own_tenants if profile else True,
            'has_active_agency': bool(relation),
            'agency_name': agency.name if agency else None,
            'agent_name': relation.agent.get_full_name() if relation else None,
        }

        actions = [
            {'action': 'add_property', 'label': 'Ajouter un bien', 'available': user.is_validated,
             'reason': None if user.is_validated else "Compte en attente de validation"},
            {'action': 'view_properties', 'label': 'Voir mes biens', 'available': True, 'reason': None},
            {'action': 'view_leases', 'label': 'Voir mes locations', 'available': True, 'reason': None},
            {'action': 'view_payments', 'label': 'Suivre mes paiements', 'available': True, 'reason': None},
            {'action': 'choose_agency', 'label': 'Confier mes biens à une agence', 'available': not bool(relation),
             'reason': None if not relation else "Vous avez déjà une agence active"},
            {'action': 'contact_agency', 'label': 'Communiquer avec mon agence', 'available': bool(relation),
             'reason': None if relation else "Aucune agence active"},
            {'action': 'terminate_mandate', 'label': 'Résilier le mandat actuel', 'available': bool(relation),
             'reason': None if relation else "Aucun mandat actif"},
            {'action': 'view_disputes', 'label': 'Voir mes litiges', 'available': True, 'reason': None},
        ]

        return Response(success_response({'status': status_data, 'available_actions': actions}))


class MandatePDFView(APIView):
    """Document PDF brande du mandat de gestion (OwnerAgentRelation) --
    telechargeable par le proprietaire ou l'agent concerne."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Owners'], summary="Télécharger le PDF d'un mandat de gestion")
    def get(self, request, relation_id):
        from django.http import HttpResponse
        from core.pdf import build_pdf

        try:
            relation = OwnerAgentRelation.objects.select_related(
                'owner', 'agent__agent_profile__agency'
            ).get(id=relation_id)
        except OwnerAgentRelation.DoesNotExist:
            return Response(error_response("Mandat introuvable"), status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if relation.owner_id != user.id and relation.agent_id != user.id:
            return Response(error_response("Accès non autorisé à ce mandat"), status=status.HTTP_403_FORBIDDEN)

        agency = relation.agent.agent_profile.agency if hasattr(relation.agent, 'agent_profile') else None
        sections = [
            (None, [
                ["Propriétaire", relation.owner.get_full_name()],
                ["Agence gestionnaire", agency.name if agency else "-"],
                ["Agent responsable", relation.agent.get_full_name()],
                ["Statut", relation.get_status_display()],
                ["Date de début", str(relation.contract_start)],
                ["Date de fin", str(relation.contract_end) if relation.contract_end else "Durée indéterminée"],
            ]),
        ]
        if relation.status == 'terminated':
            sections.append(("Résiliation", [
                ["Date", str(relation.terminated_at.date()) if relation.terminated_at else "-"],
                ["Motif", relation.termination_reason or "-"],
            ]))

        pdf_bytes = build_pdf("Mandat de gestion immobilière", str(relation.id), sections)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="mandat-{relation.id}.pdf"'
        return response
