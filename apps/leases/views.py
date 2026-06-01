from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import RentPayment, DebtRecord, Complaint
from .serializers import (
    RentPaymentSerializer, ConfirmCashPaymentSerializer,
    DebtActionSerializer, ComplaintSerializer, CreateComplaintSerializer
)
from apps.contracts.models import LeaseContract
from core.permissions import IsAgent
from core.utils import success_response, error_response, calculate_platform_commission


class MyRentPaymentsView(APIView):
    """Historique des paiements de loyer"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Mes paiements de loyer")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            payments = RentPayment.objects.filter(tenant=request.user)
        elif request.user.role == 'agent':
            payments = RentPayment.objects.filter(lease__agent=request.user)
        elif request.user.role == 'owner':
            payments = RentPayment.objects.filter(lease__owner=request.user)
        else:
            payments = RentPayment.objects.all()

        from core.pagination import StandardResultsSetPagination
        payments = payments.order_by('-due_date')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(payments, request)
        return paginator.get_paginated_response(
            RentPaymentSerializer(page, many=True).data
        )


class ConfirmCashPaymentView(APIView):
    """Agent confirme un paiement cash du locataire"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Leases'],
        summary="Confirmer paiement cash (agent)",
        request=ConfirmCashPaymentSerializer
    )
    def post(self, request):
        serializer = ConfirmCashPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payment = RentPayment.objects.get(
                id=serializer.validated_data['rent_payment_id'],
                lease__agent=request.user,
                status='pending'
            )
        except RentPayment.DoesNotExist:
            return Response(error_response("Paiement introuvable"), status=status.HTTP_404_NOT_FOUND)

        commission_data = calculate_platform_commission(float(payment.amount))

        payment.status            = 'paid'
        payment.confirmed_by_agent = True
        payment.confirmed_at      = timezone.now()
        payment.paid_at           = timezone.now()
        payment.platform_fee      = commission_data['platform_commission']
        payment.owner_amount      = commission_data['owner_amount']
        payment.notes             = serializer.validated_data.get('notes', '')
        payment.save()

        return Response(success_response(
            RentPaymentSerializer(payment).data,
            "Paiement confirmé ✅"
        ))


class DebtManagementView(APIView):
    """Agent gère une dette — prolonger ou réclamer"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Leases'],
        summary="Gérer une dette (agent)",
        request=DebtActionSerializer
    )
    def post(self, request, payment_id):
        try:
            payment = RentPayment.objects.get(
                id=payment_id,
                lease__agent=request.user,
                status__in=['pending', 'late']
            )
        except RentPayment.DoesNotExist:
            return Response(error_response("Paiement introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = DebtActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']

        debt = DebtRecord.objects.create(
            lease=payment.lease,
            rent_payment=payment,
            tenant=payment.tenant,
            agent=request.user,
            amount_owed=payment.amount,
            action_taken=action,
            new_due_date=serializer.validated_data.get('new_due_date'),
            notes=serializer.validated_data.get('notes', '')
        )

        if action == 'extend' and serializer.validated_data.get('new_due_date'):
            payment.due_date = serializer.validated_data['new_due_date']
            payment.save(update_fields=['due_date'])

        return Response(success_response(
            message=f"Action '{action}' enregistrée pour la dette de {payment.tenant.get_full_name()}"
        ))


class SubmitComplaintView(APIView):
    """Locataire soumet une plainte"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Leases'],
        summary="Soumettre une plainte",
        request=CreateComplaintSerializer
    )
    def post(self, request):
        if request.user.role not in ['client', 'tenant']:
            return Response(
                error_response("Seuls les locataires peuvent soumettre des plaintes"),
                status=status.HTTP_403_FORBIDDEN
            )

        lease = LeaseContract.objects.filter(
            tenant=request.user, status='active'
        ).first()

        if not lease:
            return Response(
                error_response("Aucun bail actif trouvé"),
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CreateComplaintSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Routing intelligent
        # Si propriétaire actif → lui assigner
        # Sinon → agent
        if lease.owner.is_validated and lease.owner.role == 'owner':
            assigned_to = lease.owner
        else:
            assigned_to = lease.agent

        complaint = serializer.save(
            lease=lease,
            tenant=request.user,
            assigned_to=assigned_to
        )

        return Response(
            success_response(
                ComplaintSerializer(complaint).data,
                f"Plainte envoyée à {assigned_to.get_full_name()}"
            ),
            status=status.HTTP_201_CREATED
        )


class MyComplaintsView(APIView):
    """Mes plaintes"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Mes plaintes")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            complaints = Complaint.objects.filter(tenant=request.user)
        else:
            complaints = Complaint.objects.filter(assigned_to=request.user)

        from core.pagination import StandardResultsSetPagination
        complaints = complaints.order_by('-created_at')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(complaints, request)
        return paginator.get_paginated_response(
            ComplaintSerializer(page, many=True).data
        )


class ResolveComplaintView(APIView):
    """Résoudre une plainte"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Résoudre une plainte")
    def post(self, request, complaint_id):
        try:
            complaint = Complaint.objects.get(
                id=complaint_id,
                assigned_to=request.user
            )
        except Complaint.DoesNotExist:
            return Response(error_response("Plainte introuvable"), status=status.HTTP_404_NOT_FOUND)

        resolution = request.data.get('resolution_note', '')
        if not resolution:
            return Response(
                error_response("Une note de résolution est obligatoire"),
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint.status          = 'resolved'
        complaint.resolution_note = resolution
        complaint.resolved_at     = timezone.now()
        complaint.save()

        return Response(success_response(
            ComplaintSerializer(complaint).data,
            "Plainte résolue ✅"
        ))
