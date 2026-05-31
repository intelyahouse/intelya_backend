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

        boost = Boost.objects.create(
            agent       = request.user,
            level       = level,
            duration_days = duration,
            target_city = data['target_city'],
            target_neighborhood = data.get('target_neighborhood', ''),
            price_paid  = price,
            is_active   = True,
            start_date  = timezone.now(),
            end_date    = timezone.now() + timedelta(days=duration),
        )

        return Response(
            success_response(
                BoostSerializer(boost).data,
                f"Boost {level.upper()} activé pour {duration} jours sur {data['target_city']} ✅"
            ),
            status=status.HTTP_201_CREATED
        )


class MyBoostsView(APIView):
    """Mes boosts actifs et historique"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Boost'], summary="Mes boosts")
    def get(self, request):
        boosts = Boost.objects.filter(agent=request.user).order_by('-created_at')

        # Désactiver automatiquement les expirés
        for boost in boosts:
            if boost.is_active and boost.is_expired():
                boost.is_active = False
                boost.save(update_fields=['is_active'])

        serializer = BoostSerializer(boosts, many=True)
        return Response(success_response(serializer.data))
