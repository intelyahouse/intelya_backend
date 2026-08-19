from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from .models import RentPayment, DebtRecord, Complaint
from .serializers import (
    RentPaymentSerializer, ConfirmCashPaymentSerializer,
    DebtActionSerializer, ComplaintSerializer, CreateComplaintSerializer
)
from apps.contracts.models import LeaseContract
from core.permissions import IsAgent
from core.utils import success_response, error_response, calculate_platform_commission
from core.pagination import StandardResultsSetPagination
import logging

logger = logging.getLogger(__name__)


class MyRentPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Mes paiements de loyer")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            payments = RentPayment.objects.filter(tenant=request.user).select_related('lease__rental_property')
        elif request.user.role == 'agent':
            agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
            payments = RentPayment.objects.filter(lease__agency_id=agency_id).select_related('tenant', 'lease__rental_property')
        elif request.user.role == 'owner':
            payments = RentPayment.objects.filter(lease__owner=request.user).select_related('tenant', 'lease__rental_property')
        else:
            payments = RentPayment.objects.all().select_related('tenant', 'lease')

        paginator  = StandardResultsSetPagination()
        page_data  = paginator.paginate_queryset(payments.order_by('-due_date'), request)
        serializer = RentPaymentSerializer(page_data, many=True)
        return paginator.get_paginated_response(serializer.data)


class ConfirmCashPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Leases'], summary="Confirmer paiement cash (agent)", request=ConfirmCashPaymentSerializer)
    def post(self, request):
        serializer = ConfirmCashPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        try:
            payment = RentPayment.objects.select_related(
                'tenant', 'lease__owner__owner_profile'
            ).get(
                id=serializer.validated_data['rent_payment_id'],
                lease__agency_id=agency_id,
                status='pending'
            )
        except RentPayment.DoesNotExist:
            return Response(error_response("Paiement introuvable"), status=status.HTTP_404_NOT_FOUND)

        commission_data = calculate_platform_commission(float(payment.amount))

        with transaction.atomic():
            payment.status             = 'paid'
            payment.confirmed_by_agent = True
            payment.confirmed_at       = timezone.now()
            payment.paid_at            = timezone.now()
            payment.platform_fee       = commission_data['platform_commission']
            payment.owner_amount       = commission_data['owner_amount']
            payment.notes              = serializer.validated_data.get('notes', '')
            payment.save()

        return Response(success_response(RentPaymentSerializer(payment).data, "Paiement confirmé ✅"))


class DebtManagementView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Leases'], summary="Gérer une dette (agent)", request=DebtActionSerializer)
    def post(self, request, payment_id):
        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        try:
            payment = RentPayment.objects.select_related(
                'tenant', 'lease'
            ).get(
                id=payment_id, lease__agency_id=agency_id,
                status__in=['pending', 'late']
            )
        except RentPayment.DoesNotExist:
            return Response(error_response("Paiement introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = DebtActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']

        with transaction.atomic():
            DebtRecord.objects.create(
                lease=payment.lease, rent_payment=payment,
                tenant=payment.tenant, agent=request.user,
                amount_owed=payment.amount, action_taken=action,
                new_due_date=serializer.validated_data.get('new_due_date'),
                notes=serializer.validated_data.get('notes', '')
            )

            update_fields = []
            if action == 'extend' and serializer.validated_data.get('new_due_date'):
                payment.due_date = serializer.validated_data['new_due_date']
                update_fields.append('due_date')
                payment.status = 'pending'
                update_fields.append('status')
            elif action == 'claim':
                payment.status = 'disputed'
                update_fields.append('status')

            if update_fields:
                payment.save(update_fields=update_fields)

        return Response(success_response(
            RentPaymentSerializer(payment).data,
            f"Action '{action}' enregistrée"
        ))


class SubmitComplaintView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Soumettre une plainte", request=CreateComplaintSerializer)
    def post(self, request):
        if request.user.role not in ['client', 'tenant']:
            return Response(error_response("Seuls les locataires peuvent soumettre des plaintes"), status=status.HTTP_403_FORBIDDEN)

        lease = LeaseContract.objects.filter(
            tenant=request.user, status='active'
        ).select_related('owner', 'agent', 'agency').first()

        if not lease:
            return Response(error_response("Aucun bail actif trouvé"), status=status.HTTP_404_NOT_FOUND)

        serializer = CreateComplaintSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        assigned_to = lease.owner if (lease.owner.is_validated and lease.owner.role == 'owner') else lease.agent

        complaint = serializer.save(lease=lease, tenant=request.user, assigned_to=assigned_to, agency=lease.agency)

        from apps.notifications.utils import notify_complaint_new
        notify_complaint_new(assigned_to, request.user.get_full_name(), complaint.category)

        return Response(
            success_response(ComplaintSerializer(complaint).data, f"Plainte envoyée à {assigned_to.get_full_name()}"),
            status=status.HTTP_201_CREATED
        )


class MyComplaintsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Mes plaintes")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            complaints = Complaint.objects.filter(tenant=request.user).select_related('assigned_to', 'lease__rental_property')
        elif request.user.role == 'agent':
            agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
            complaints = Complaint.objects.filter(
                Q(assigned_to=request.user) | Q(agency_id=agency_id)
            ).select_related('tenant', 'lease__rental_property')
        else:
            complaints = Complaint.objects.filter(assigned_to=request.user).select_related('tenant', 'lease__rental_property')

        paginator  = StandardResultsSetPagination()
        page_data  = paginator.paginate_queryset(complaints.order_by('-created_at'), request)
        serializer = ComplaintSerializer(page_data, many=True)
        return paginator.get_paginated_response(serializer.data)


class ResolveComplaintView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Résoudre une plainte")
    def post(self, request, complaint_id):
        try:
            complaint = Complaint.objects.select_related('tenant', 'assigned_to').get(id=complaint_id)
        except (Complaint.DoesNotExist, ValueError):
            return Response(error_response("Plainte introuvable"), status=status.HTTP_404_NOT_FOUND)

        # Autorise le destinataire exact, ou -- si la plainte a ete confiee a
        # un agent (pas au proprietaire) -- n'importe quel agent de la meme
        # agence, coherent avec le principe agence-large des autres phases.
        can_resolve = complaint.assigned_to_id == request.user.id
        if not can_resolve and request.user.role == 'agent' and complaint.assigned_to and complaint.assigned_to.role == 'agent':
            agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
            can_resolve = agency_id is not None and agency_id == complaint.agency_id

        if not can_resolve:
            return Response(error_response("Plainte introuvable"), status=status.HTTP_404_NOT_FOUND)

        resolution = request.data.get('resolution_note', '').strip()
        if not resolution:
            return Response(error_response("Note de résolution obligatoire"), status=status.HTTP_400_BAD_REQUEST)

        complaint.status          = 'resolved'
        complaint.resolution_note = resolution
        complaint.resolved_at     = timezone.now()
        complaint.save()

        return Response(success_response(ComplaintSerializer(complaint).data, "Plainte résolue ✅"))
