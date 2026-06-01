from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta
from drf_spectacular.utils import extend_schema
from .models import Transaction, Escrow
from .serializers import TransactionSerializer, InitiatePaymentSerializer
from .services.campay import campay_service
from .services.bank import bank_service
from core.utils import success_response, error_response, generate_transaction_reference, calculate_platform_commission
from core.throttles import PaymentThrottle
from core.permissions import IsAdmin
import logging

logger = logging.getLogger(__name__)


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [PaymentThrottle]

    @extend_schema(tags=['Payments'], summary="Initier un paiement", request=InitiatePaymentSerializer)
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        data         = serializer.validated_data
        amount       = float(data['amount'])
        method       = data['payment_method']
        phone        = data.get('phone_number', request.user.phone)
        related_type = data['related_type']
        related_id   = data['related_id']

        # Vérifier montant minimum
        if amount < 100:
            return Response(error_response("Montant minimum: 100 FCFA"), status=status.HTTP_400_BAD_REQUEST)

        # Clé d'idempotence — empêche double paiement
        idempotency_key = f"{request.user.id}_{related_type}_{related_id}"
        existing = Transaction.objects.filter(
            external_reference=idempotency_key,
            status__in=['pending', 'processing', 'completed']
        ).first()
        if existing:
            return Response(success_response(
                TransactionSerializer(existing).data,
                "Transaction déjà en cours"
            ))

        commission_data = calculate_platform_commission(amount)
        reference = generate_transaction_reference()

        # TRANSACTION ATOMIQUE — tout ou rien
        try:
            with transaction.atomic():
                txn = Transaction.objects.create(
                    reference=reference,
                    payer=request.user,
                    transaction_type=related_type,
                    amount=amount,
                    platform_fee=commission_data['platform_commission'],
                    net_amount=commission_data['owner_amount'],
                    currency='FCFA',
                    status='pending',
                    payment_method=method,
                    external_reference=idempotency_key,
                    description=f"Paiement {related_type} INTELYA HAVEN",
                )

                if related_type == 'visit':
                    txn.related_visit_id = related_id
                else:
                    txn.related_lease_id = related_id
                txn.save(update_fields=['related_visit_id', 'related_lease_id'])

        except Exception as e:
            logger.error(f"[PAYMENT] Erreur création transaction: {e}")
            return Response(error_response("Erreur lors de l'initiation du paiement"), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Appeler l'API paiement (hors transaction atomique)
        payment_result = None
        if method in ['mtn', 'orange']:
            payment_result = campay_service.collect(phone=phone, amount=int(amount), reference=reference)
        elif method == 'bank':
            payment_result = bank_service.initiate_payment(account_number=phone, amount=int(amount), reference=reference)

        if payment_result and payment_result.get('success'):
            txn.status = 'processing'
            txn.external_reference = payment_result.get('reference', idempotency_key)
            txn.save(update_fields=['status', 'external_reference'])

            if related_type == 'visit':
                Escrow.objects.create(
                    transaction=txn,
                    amount=amount,
                    held_for=request.user,
                    release_after=timezone.now() + timedelta(hours=24)
                )

        # Log audit
        from core.audit import log_payment_initiated
        log_payment_initiated(request.user, reference, amount, method, request)

        return Response(success_response(
            {'transaction_id': str(txn.id), 'reference': reference, 'status': txn.status,
             'ussd_code': payment_result.get('ussd_code', '') if payment_result else ''},
            "Paiement initié ✅"
        ), status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class CampayWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        import hmac, hashlib
        signature = request.headers.get('X-Campay-Signature', '')
        secret = getattr(__import__('django.conf', fromlist=['settings']).settings, 'CAMPAY_WEBHOOK_SECRET', '')

        if secret:
            expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning("[WEBHOOK] Signature invalide")
                return Response({'status': 'invalid_signature'}, status=401)

        data = request.data
        reference = data.get('reference') or data.get('external_reference')
        status_ = data.get('status', '').upper()

        if not reference:
            return Response({'status': 'ignored'})

        try:
            txn = Transaction.objects.get(external_reference=reference)
        except Transaction.DoesNotExist:
            try:
                txn = Transaction.objects.get(reference=reference)
            except Transaction.DoesNotExist:
                return Response({'status': 'not_found'})

        # TRANSACTION ATOMIQUE — webhook
        with transaction.atomic():
            txn.webhook_data = data
            if status_ in ['SUCCESSFUL', 'SUCCESS', 'COMPLETED']:
                txn.status = 'completed'
                txn.completed_at = timezone.now()
                txn.save()

                if hasattr(txn, 'escrow'):
                    txn.escrow.status = 'released'
                    txn.escrow.released_at = timezone.now()
                    txn.escrow.save()

                self._process_owner_transfer(txn)

            elif status_ in ['FAILED', 'CANCELLED', 'EXPIRED']:
                txn.status = 'failed'
                txn.save()
                if hasattr(txn, 'escrow'):
                    txn.escrow.status = 'refunded'
                    txn.escrow.released_at = timezone.now()
                    txn.escrow.save()
            else:
                txn.save(update_fields=['webhook_data'])

        return Response({'status': 'ok'})

    def _process_owner_transfer(self, txn):
        if txn.transaction_type != 'rent' or not txn.related_lease_id:
            return
        try:
            from apps.contracts.models import LeaseContract
            lease = LeaseContract.objects.select_related('owner__owner_profile').get(id=txn.related_lease_id)
            owner_profile = lease.owner.owner_profile
            phone = owner_profile.mtn_momo_number or owner_profile.orange_money_number
            if phone and float(txn.net_amount) > 0:
                campay_service.disburse(phone=phone, amount=int(txn.net_amount), reference=f"OWNER-{txn.reference}")
        except Exception as e:
            logger.error(f"[VIREMENT PROPRIO] Erreur: {e}")


class MyTransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from core.pagination import StandardResultsSetPagination
        txns = Transaction.objects.filter(
            Q(payer=request.user) | Q(receiver=request.user)
        ).order_by('-created_at').select_related('payer', 'receiver')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(txns, request)
        return paginator.get_paginated_response(
            TransactionSerializer(page, many=True).data
        )


class CheckPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        try:
            txn = Transaction.objects.get(reference=reference, payer=request.user)
        except Transaction.DoesNotExist:
            return Response(error_response("Transaction introuvable"), status=status.HTTP_404_NOT_FOUND)

        if txn.status == 'processing' and txn.external_reference:
            result = campay_service.check_status(txn.external_reference)
            if result.get('success') and result.get('status', '').upper() in ['SUCCESSFUL', 'COMPLETED']:
                with transaction.atomic():
                    txn.status = 'completed'
                    txn.completed_at = timezone.now()
                    txn.save()

        return Response(success_response(TransactionSerializer(txn).data))
