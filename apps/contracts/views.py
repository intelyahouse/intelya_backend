from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import AgentOwnerContract, LeaseContract
from .serializers import (
    AgentOwnerContractSerializer,
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

        lease = serializer.save(
            agent=request.user,
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
            leases = LeaseContract.objects.filter(agent=user)
        elif user.role == 'owner':
            leases = LeaseContract.objects.filter(owner=user)
        else:
            leases = LeaseContract.objects.all()

        serializer = LeaseContractSerializer(leases, many=True)
        return Response(success_response(serializer.data))
