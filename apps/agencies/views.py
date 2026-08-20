from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from core.permissions import IsAgent
from core.utils import success_response, error_response
from apps.agents.models import AgentProfile
from apps.notifications.utils import (
    notify_agency_invitation, notify_agency_invitation_accepted,
    notify_agency_invitation_declined, notify_agency_member_removed,
    notify_mandate_reassigned,
)
from .models import AgencyInvitation
from .serializers import AgencySerializer, AgencyInvitationSerializer, AgencyPaymentInfoSerializer
from .services import transfer_agent_to_agency, remove_agent_from_agency


def _get_agent_profile(request):
    try:
        return request.user.agent_profile
    except AgentProfile.DoesNotExist:
        return None


def _is_gerant(user, agency):
    return agency.owner_agent_id == user.id


class AgencyMeView(APIView):
    """Mon agence — details et membres"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Mon agence")
    def get(self, request):
        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)
        return Response(success_response(AgencySerializer(profile.agency).data))

    @extend_schema(tags=['Agencies'], summary="Mettre a jour les coordonnees de paiement de l'agence")
    def patch(self, request):
        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)
        agency = profile.agency

        if not _is_gerant(request.user, agency):
            return Response(
                error_response("Seul le gerant peut modifier les coordonnees de paiement de l'agence"),
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AgencyPaymentInfoSerializer(agency, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        return Response(success_response(AgencySerializer(agency).data, "Coordonnées de paiement mises à jour"))


class AgencyInviteView(APIView):
    """Le gerant invite un agent a rejoindre son agence, ou consulte les invitations envoyees"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Inviter un agent dans mon agence")
    def post(self, request):
        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)
        agency = profile.agency

        if not _is_gerant(request.user, agency):
            return Response(
                error_response("Seul le gerant de l'agence peut inviter un agent"),
                status=status.HTTP_403_FORBIDDEN
            )

        agent_profile_id = request.data.get('agent_profile_id')
        try:
            target_profile = AgentProfile.objects.select_related('user', 'agency').get(id=agent_profile_id)
        except (AgentProfile.DoesNotExist, ValueError, TypeError):
            return Response(error_response("Agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        if target_profile.user_id == request.user.id:
            return Response(
                error_response("Vous ne pouvez pas vous inviter vous-meme"),
                status=status.HTTP_400_BAD_REQUEST
            )
        if target_profile.agency_id == agency.id:
            return Response(
                error_response("Cet agent fait deja partie de votre agence"),
                status=status.HTTP_400_BAD_REQUEST
            )
        if not target_profile.agency.is_solo:
            return Response(
                error_response("Cet agent appartient deja a une autre agence multi-agents"),
                status=status.HTTP_400_BAD_REQUEST
            )
        if AgencyInvitation.objects.filter(invited_user=target_profile.user, status='pending').exists():
            return Response(
                error_response("Cet agent a deja une invitation en attente"),
                status=status.HTTP_400_BAD_REQUEST
            )

        invitation = AgencyInvitation.objects.create(
            agency=agency, invited_user=target_profile.user, invited_by=request.user,
        )
        notify_agency_invitation(target_profile.user, agency.name, request.user.get_full_name())

        return Response(success_response(
            AgencyInvitationSerializer(invitation).data, "Invitation envoyee"
        ), status=status.HTTP_201_CREATED)

    @extend_schema(tags=['Agencies'], summary="Invitations envoyees par mon agence")
    def get(self, request):
        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)
        agency = profile.agency
        if not _is_gerant(request.user, agency):
            return Response(
                error_response("Seul le gerant peut consulter les invitations envoyees"),
                status=status.HTTP_403_FORBIDDEN
            )
        invitations = AgencyInvitation.objects.filter(agency=agency).select_related(
            'invited_user', 'invited_by', 'agency'
        ).order_by('-created_at')
        return Response(success_response(AgencyInvitationSerializer(invitations, many=True).data))


class AgencyInvitationCancelView(APIView):
    """Annuler une invitation envoyee (gerant uniquement)"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Annuler une invitation envoyee")
    def delete(self, request, invitation_id):
        try:
            invitation = AgencyInvitation.objects.select_related('agency').get(
                id=invitation_id, status='pending'
            )
        except (AgencyInvitation.DoesNotExist, ValueError):
            return Response(error_response("Invitation introuvable"), status=status.HTTP_404_NOT_FOUND)

        if not _is_gerant(request.user, invitation.agency):
            return Response(
                error_response("Seul le gerant peut annuler cette invitation"),
                status=status.HTTP_403_FORBIDDEN
            )

        invitation.status = 'cancelled'
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at'])
        return Response(success_response(message="Invitation annulee"))


class MyAgencyInvitationsView(APIView):
    """Invitations que j'ai recues en tant qu'agent"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Invitations que j'ai recues")
    def get(self, request):
        invitations = AgencyInvitation.objects.filter(
            invited_user=request.user, status='pending'
        ).select_related('agency', 'invited_by').order_by('-created_at')
        return Response(success_response(AgencyInvitationSerializer(invitations, many=True).data))


class RespondAgencyInvitationView(APIView):
    """Accepter ou refuser une invitation recue"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Repondre a une invitation d'agence")
    def post(self, request, invitation_id):
        action = request.data.get('action')
        if action not in ('accept', 'decline'):
            return Response(
                error_response("Action invalide. Utilisez 'accept' ou 'decline'"),
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            invitation = AgencyInvitation.objects.select_related('agency', 'invited_by').get(
                id=invitation_id, invited_user=request.user, status='pending'
            )
        except (AgencyInvitation.DoesNotExist, ValueError):
            return Response(error_response("Invitation introuvable"), status=status.HTTP_404_NOT_FOUND)

        if action == 'decline':
            invitation.status = 'declined'
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=['status', 'responded_at'])
            notify_agency_invitation_declined(invitation.invited_by, request.user.get_full_name())
            return Response(success_response(message="Invitation refusee"))

        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        if profile.agency_id == invitation.agency_id:
            return Response(
                error_response("Vous faites deja partie de cette agence"),
                status=status.HTTP_400_BAD_REQUEST
            )
        if not profile.agency.is_solo:
            return Response(
                error_response("Vous devez d'abord quitter votre agence actuelle"),
                status=status.HTTP_400_BAD_REQUEST
            )

        transfer_agent_to_agency(profile, invitation.agency)
        invitation.status = 'accepted'
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at'])
        notify_agency_invitation_accepted(invitation.invited_by, request.user.get_full_name())

        return Response(success_response(
            AgencySerializer(invitation.agency).data,
            f"Vous avez rejoint {invitation.agency.name}"
        ))


class AgencyMemberRemoveView(APIView):
    """Le gerant retire un agent de son agence"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Retirer un agent de mon agence")
    def post(self, request, user_id):
        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)
        agency = profile.agency

        if not _is_gerant(request.user, agency):
            return Response(
                error_response("Seul le gerant peut retirer un agent"),
                status=status.HTTP_403_FORBIDDEN
            )
        if str(user_id) == str(request.user.id):
            return Response(
                error_response("Le gerant ne peut pas se retirer lui-meme de son agence"),
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            member_profile = AgentProfile.objects.select_related('user').get(user_id=user_id, agency=agency)
        except (AgentProfile.DoesNotExist, ValueError):
            return Response(
                error_response("Cet agent ne fait pas partie de votre agence"),
                status=status.HTTP_404_NOT_FOUND
            )

        agency_name = agency.name
        member_name = member_profile.user.get_full_name()
        remove_agent_from_agency(member_profile)
        notify_agency_member_removed(member_profile.user, agency_name)

        return Response(success_response(message=f"{member_name} a ete retire de l'agence"))


class AgencyLeaveView(APIView):
    """Un agent (non-gerant) quitte volontairement son agence"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Quitter mon agence")
    def post(self, request):
        profile = _get_agent_profile(request)
        if not profile:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)
        agency = profile.agency

        if _is_gerant(request.user, agency):
            return Response(
                error_response("Le gerant ne peut pas quitter sa propre agence"),
                status=status.HTTP_400_BAD_REQUEST
            )

        agency_name = agency.name
        remove_agent_from_agency(profile)
        return Response(success_response(message=f"Vous avez quitte {agency_name}"))


class MandateReassignView(APIView):
    """Reaffecter un mandat proprietaire a un autre agent de la meme agence
    (gerant, ou l'agent actuellement en charge du dossier)"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Reaffecter un mandat a un autre agent de mon agence")
    def post(self, request, relation_id):
        from apps.agents.models import OwnerAgentRelation, AgentProfile

        try:
            relation = OwnerAgentRelation.objects.select_related('agency', 'agent', 'owner').get(
                id=relation_id, status='active'
            )
        except (OwnerAgentRelation.DoesNotExist, ValueError):
            return Response(error_response("Mandat introuvable"), status=status.HTTP_404_NOT_FOUND)

        agency = relation.agency
        if not (_is_gerant(request.user, agency) or relation.agent_id == request.user.id):
            return Response(
                error_response("Seul le gerant ou l'agent en charge peut reaffecter ce mandat"),
                status=status.HTTP_403_FORBIDDEN
            )

        new_agent_profile_id = request.data.get('agent_profile_id')
        try:
            new_profile = AgentProfile.objects.select_related('user').get(
                id=new_agent_profile_id, agency=agency
            )
        except (AgentProfile.DoesNotExist, ValueError, TypeError):
            return Response(
                error_response("Cet agent ne fait pas partie de votre agence"),
                status=status.HTTP_404_NOT_FOUND
            )

        if new_profile.user_id == relation.agent_id:
            return Response(
                error_response("Ce mandat est deja affecte a cet agent"),
                status=status.HTTP_400_BAD_REQUEST
            )

        relation.agent = new_profile.user
        relation.save(update_fields=['agent'])
        notify_mandate_reassigned(new_profile.user, relation.owner.get_full_name())

        return Response(success_response(
            message=f"Mandat reaffecte a {new_profile.user.get_full_name()}"
        ))


class ClientReassignView(APIView):
    """Reaffecter un client a un autre agent de la meme agence
    (gerant, ou l'agent actuellement en charge du client)"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agencies'], summary="Reaffecter un client a un autre agent de mon agence")
    def post(self, request, relation_id):
        from apps.agents.models import ClientAgentRelation, AgentProfile

        try:
            relation = ClientAgentRelation.objects.select_related('agency', 'agent', 'client').get(
                id=relation_id, is_active=True
            )
        except (ClientAgentRelation.DoesNotExist, ValueError):
            return Response(error_response("Relation client introuvable"), status=status.HTTP_404_NOT_FOUND)

        agency = relation.agency
        if not (_is_gerant(request.user, agency) or relation.agent_id == request.user.id):
            return Response(
                error_response("Seul le gerant ou l'agent en charge peut reaffecter ce client"),
                status=status.HTTP_403_FORBIDDEN
            )

        new_agent_profile_id = request.data.get('agent_profile_id')
        try:
            new_profile = AgentProfile.objects.select_related('user').get(
                id=new_agent_profile_id, agency=agency
            )
        except (AgentProfile.DoesNotExist, ValueError, TypeError):
            return Response(
                error_response("Cet agent ne fait pas partie de votre agence"),
                status=status.HTTP_404_NOT_FOUND
            )

        if new_profile.user_id == relation.agent_id:
            return Response(
                error_response("Ce client est deja affecte a cet agent"),
                status=status.HTTP_400_BAD_REQUEST
            )

        relation.agent = new_profile.user
        relation.save(update_fields=['agent'])
        notify_mandate_reassigned(new_profile.user, relation.client.get_full_name())

        return Response(success_response(
            message=f"Client reaffecte a {new_profile.user.get_full_name()}"
        ))
