from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import AgentOwnerContract, LeaseContract
from .serializers import (
    AgentOwnerContractSerializer,
    CreateAgentOwnerContractSerializer,
    CreateLeaseSerializer,
    LeaseContractSerializer
)
from core.permissions import IsAgent, IsAdmin
from core.utils import success_response, error_response


class CreateLeaseView(APIView):
    """Agent crée un bail pour un client"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Contracts'],
        summary="Créer un bail (agent)",
        request=CreateLeaseSerializer
    )
    def post(self, request):
        serializer = CreateLeaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.conf import settings
        from apps.agents.models import ClientAgentRelation

        # Vérifier que le tenant appartient bien à l'agence de cet agent
        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        tenant_id = serializer.validated_data.get('tenant').id
        if not ClientAgentRelation.objects.filter(
            client_id=tenant_id,
            agency_id=agency_id,
            is_active=True
        ).exists():
            return Response(
                error_response("Ce client n'est pas lié à votre agence"),
                status=status.HTTP_403_FORBIDDEN
            )

        agency = getattr(getattr(request.user, 'agent_profile', None), 'agency', None)
        lease = serializer.save(
            agent=request.user, agency=agency,
            platform_fee_percent=settings.PLATFORM_COMMISSION_PERCENT
        )

        # Mettre le bien en statut "Loué"
        lease.rental_property.status = 'rented'
        lease.rental_property.save(update_fields=['status'])

        # Changer le rôle du client en locataire
        tenant = lease.tenant
        tenant.role = 'tenant'
        tenant.save(update_fields=['role'])

        return Response(
            success_response(
                LeaseContractSerializer(lease).data,
                "Bail créé avec succès"
            ),
            status=status.HTTP_201_CREATED
        )


class SignLeaseView(APIView):
    """Signer le bail"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Contracts'], summary="Signer le bail")
    def post(self, request, lease_id):
        try:
            lease = LeaseContract.objects.get(id=lease_id)
        except LeaseContract.DoesNotExist:
            return Response(error_response("Bail introuvable"), status=status.HTTP_404_NOT_FOUND)

        user = request.user

        if user == lease.tenant:
            lease.signed_by_tenant = True
        elif user == lease.owner:
            lease.signed_by_owner = True
        else:
            return Response(error_response("Non autorisé"), status=status.HTTP_403_FORBIDDEN)

        if lease.is_fully_signed():
            lease.status = 'active'
            lease.signed_at = timezone.now()

        lease.save()

        return Response(success_response(
            LeaseContractSerializer(lease).data,
            "Bail signé ✅" if lease.is_fully_signed() else "Signature enregistrée. En attente de l'autre partie."
        ))


class MyLeasesView(APIView):
    """Mes baux"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Contracts'], summary="Mes baux")
    def get(self, request):
        user = request.user
        if user.role in ['client', 'tenant']:
            leases = LeaseContract.objects.filter(tenant=user)
        elif user.role == 'agent':
            agency_id = getattr(getattr(user, 'agent_profile', None), 'agency_id', None)
            leases = LeaseContract.objects.filter(agency_id=agency_id) if agency_id else LeaseContract.objects.none()
        elif user.role == 'owner':
            leases = LeaseContract.objects.filter(owner=user)
        else:
            leases = LeaseContract.objects.all()

        serializer = LeaseContractSerializer(leases, many=True)
        return Response(success_response(serializer.data))


class LeaseContractPDFView(APIView):
    """Document PDF brande du contrat de bail -- telechargeable par le
    locataire, le proprietaire, ou un agent de l'agence gestionnaire."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Contracts'], summary="Télécharger le PDF d'un contrat de bail")
    def get(self, request, lease_id):
        from django.http import HttpResponse
        from core.pdf import build_pdf
        from core.utils import format_fcfa

        try:
            lease = LeaseContract.objects.select_related('tenant', 'owner', 'agent', 'rental_property').get(id=lease_id)
        except LeaseContract.DoesNotExist:
            return Response(error_response("Bail introuvable"), status=status.HTTP_404_NOT_FOUND)

        user = request.user
        agency_id = getattr(getattr(user, 'agent_profile', None), 'agency_id', None)
        allowed = (
            lease.tenant_id == user.id or
            lease.owner_id == user.id or
            (agency_id and lease.agency_id == agency_id)
        )
        if not allowed:
            return Response(error_response("Accès non autorisé à ce contrat"), status=status.HTTP_403_FORBIDDEN)

        sections = [
            ("Parties", [
                ["Locataire", lease.tenant.get_full_name()],
                ["Propriétaire", lease.owner.get_full_name()],
                ["Agent responsable", lease.agent.get_full_name() if lease.agent else "-"],
            ]),
            ("Bien loué", [
                ["Bien", lease.rental_property.title],
                ["Ville", lease.rental_property.city],
                ["Quartier", lease.rental_property.neighborhood],
            ]),
            ("Conditions", [
                ["Loyer mensuel", format_fcfa(lease.monthly_rent)],
                ["Caution", format_fcfa(lease.deposit_amount)],
                ["Date de début", str(lease.start_date)],
                ["Date de fin", str(lease.end_date)],
                ["Jour de paiement", str(lease.payment_day)],
                ["Statut", lease.get_status_display()],
                ["Signé par le locataire", "Oui" if lease.signed_by_tenant else "Non"],
                ["Signé par le propriétaire", "Oui" if lease.signed_by_owner else "Non"],
            ]),
        ]
        pdf_bytes = build_pdf("Contrat de bail", str(lease.id), sections)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="bail-{lease.id}.pdf"'
        return response


class CreateAgentOwnerContractView(APIView):
    """Agent formalise un contrat avec un proprietaire dont il a le mandat
    actif (OwnerAgentRelation) -- distinct du mandat lui-meme : ce contrat
    porte les conditions precises (commission, duree, termes) et se signe
    electroniquement des deux cotes, comme un bail."""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Contracts'], summary="Créer un contrat agent-propriétaire", request=CreateAgentOwnerContractSerializer)
    def post(self, request):
        serializer = CreateAgentOwnerContractSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        from apps.agents.models import OwnerAgentRelation
        agency = getattr(getattr(request.user, 'agent_profile', None), 'agency', None)
        owner = serializer.validated_data['owner']

        if not OwnerAgentRelation.objects.filter(
            owner=owner, agency=agency, status='active'
        ).exists():
            return Response(
                error_response("Ce propriétaire n'a pas de mandat actif avec votre agence"),
                status=status.HTTP_403_FORBIDDEN
            )

        contract = serializer.save(agent=request.user, agency=agency)
        return Response(
            success_response(AgentOwnerContractSerializer(contract).data, "Contrat créé — en attente des signatures"),
            status=status.HTTP_201_CREATED
        )


class SignAgentOwnerContractView(APIView):
    """Signer le contrat agent-propriétaire"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Contracts'], summary="Signer un contrat agent-propriétaire")
    def post(self, request, contract_id):
        try:
            contract = AgentOwnerContract.objects.get(id=contract_id)
        except AgentOwnerContract.DoesNotExist:
            return Response(error_response("Contrat introuvable"), status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if user == contract.agent:
            contract.signed_by_agent = True
        elif user == contract.owner:
            contract.signed_by_owner = True
        else:
            return Response(error_response("Non autorisé"), status=status.HTTP_403_FORBIDDEN)

        if contract.is_fully_signed():
            contract.signed_at = timezone.now()

        contract.save()

        return Response(success_response(
            AgentOwnerContractSerializer(contract).data,
            "Contrat signé ✅" if contract.is_fully_signed() else "Signature enregistrée. En attente de l'autre partie."
        ))


class MyAgentOwnerContractsView(APIView):
    """Mes contrats agent-propriétaire"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Contracts'], summary="Mes contrats agent-propriétaire")
    def get(self, request):
        user = request.user
        if user.role == 'agent':
            contracts = AgentOwnerContract.objects.filter(agent=user)
        elif user.role == 'owner':
            contracts = AgentOwnerContract.objects.filter(owner=user)
        else:
            contracts = AgentOwnerContract.objects.none()

        return Response(success_response(AgentOwnerContractSerializer(contracts, many=True).data))


class AgentOwnerContractPDFView(APIView):
    """Document PDF brande du contrat agent-propriétaire."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Contracts'], summary="Télécharger le PDF d'un contrat agent-propriétaire")
    def get(self, request, contract_id):
        from django.http import HttpResponse
        from core.pdf import build_pdf

        try:
            contract = AgentOwnerContract.objects.select_related('agent', 'owner', 'agency').get(id=contract_id)
        except AgentOwnerContract.DoesNotExist:
            return Response(error_response("Contrat introuvable"), status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if contract.agent_id != user.id and contract.owner_id != user.id:
            return Response(error_response("Accès non autorisé à ce contrat"), status=status.HTTP_403_FORBIDDEN)

        sections = [
            (None, [
                ["Agence", contract.agency.name if contract.agency else "-"],
                ["Agent", contract.agent.get_full_name()],
                ["Propriétaire", contract.owner.get_full_name()],
                ["Statut", contract.get_status_display()],
            ]),
            ("Conditions", [
                ["Commission", f"{contract.commission_percent}%"],
                ["Date de début", str(contract.start_date)],
                ["Date de fin", str(contract.end_date) if contract.end_date else "Durée indéterminée"],
                ["Termes", contract.terms or "-"],
                ["Signé par l'agent", "Oui" if contract.signed_by_agent else "Non"],
                ["Signé par le propriétaire", "Oui" if contract.signed_by_owner else "Non"],
            ]),
        ]
        pdf_bytes = build_pdf("Contrat Agent-Propriétaire", str(contract.id), sections)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="contrat-agent-proprietaire-{contract.id}.pdf"'
        return response
