from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema
from .models import Boost
from .serializers import BoostSerializer, CreateBoostSerializer
from core.permissions import IsAgent
from core.utils import success_response, error_response, generate_transaction_reference


class BoostPricesView(APIView):
    """Grille tarifaire des boosts"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Boost'], summary="Tarifs des boosts")
    def get(self, request):
        return Response(success_response({
            'prices': Boost.PRICES,
            'currency': 'FCFA',
            'levels': {
                'bronze': 'Apparaît avant les non-boostés',
                'silver': 'Apparaît avant Bronze',
                'gold':   'Apparaît en premier — badge Or visible',
            }
        }))


class ActivateBoostView(APIView):
    """Agent active un boost"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Boost'],
        summary="Activer un boost (agent)",
        request=CreateBoostSerializer
    )
    def post(self, request):
        serializer = CreateBoostSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        data          = serializer.validated_data
        level         = data['level']
        duration      = data['duration_days']
        price         = Boost.get_price(level, duration)

        # Désactiver les boosts actifs sur la même ville
        Boost.objects.filter(
            agent=request.user,
            target_city=data['target_city'],
            is_active=True
        ).update(is_active=False)

        # Vérifier le paiement avant d'activer le boost
        from apps.payments.models import Transaction
        from core.utils import generate_transaction_reference
        from apps.payments.services.campay import campay_service

        phone = data.get('phone_number', request.user.phone)
        reference = generate_transaction_reference()

        # Initier le paiement du boost
        payment_result = campay_service.collect(
            phone=phone,
            amount=int(price),
            reference=reference,
            description=f"Boost {level.upper()} INTELYA HAVEN"
        )

        # Créer la transaction boost
        Transaction.objects.create(
            reference=reference,
            payer=request.user,
            transaction_type='boost',
            amount=price,
            platform_fee=price,
            net_amount=0,
            currency='FCFA',
            status='processing' if payment_result.get('success') else 'pending',
            payment_method=data.get('payment_method', 'mtn'),
        )

        boost = Boost.objects.create(
            agent               = request.user,
            level               = level,
            duration_days       = duration,
            target_city         = data['target_city'],
            target_neighborhood = data.get('target_neighborhood', ''),
            price_paid          = price,
            is_active           = False,  # Activé après confirmation paiement
            start_date          = timezone.now(),
            end_date            = timezone.now() + timedelta(days=duration),
            payment_reference   = reference,
        )

        msg = f"Boost {level.upper()} en attente de paiement. Validez {int(price)} FCFA sur votre téléphone."
        if not payment_result.get('success'):
            msg = f"Boost {level.upper()} créé (mode test). En production, le paiement sera requis."
            boost.is_active = True
            boost.save(update_fields=['is_active'])

        return Response(
            success_response(BoostSerializer(boost).data, msg),
            status=status.HTTP_201_CREATED
        )


class MyBoostsView(APIView):
    """Mes boosts actifs et historique"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Boost'], summary="Mes boosts")
    def get(self, request):
        boosts = Boost.objects.filter(agent=request.user).order_by('-created_at')

        # Désactiver en une seule requête SQL
        now = timezone.now()
        Boost.objects.filter(
            agent=request.user,
            is_active=True,
            end_date__lte=now
        ).update(is_active=False)

        boosts = Boost.objects.filter(agent=request.user).order_by('-created_at')
        serializer = BoostSerializer(boosts, many=True)
        return Response(success_response(serializer.data))
