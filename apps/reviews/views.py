from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema
from .models import Review
from .serializers import ReviewSerializer, CreateReviewSerializer
from apps.visits.models import VisitRequest
from core.utils import success_response, error_response


class PropertyReviewsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=['Reviews'], summary="Avis d'un bien")
    def get(self, request, property_id):
        reviews = Review.objects.filter(
            rental_property_id=property_id,
            gps_verified=True
        ).select_related('reviewer')
        from django.db.models import Avg
        avg = reviews.aggregate(avg=Avg('property_rating'))['avg']
        avg_rating = round(avg, 1) if avg else None
        return Response(success_response({
            'average_rating': avg_rating,
            'total_reviews': reviews.count(),
            'reviews': ReviewSerializer(reviews[:50], many=True).data
        }))


class AgentReviewsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=['Reviews'], summary="Avis d'un agent")
    def get(self, request, agent_id):
        reviews = Review.objects.filter(
            agent_id=agent_id,
            gps_verified=True
        ).select_related('reviewer')
        from django.db.models import Avg
        avg_data = reviews.aggregate(avg=Avg('agent_rating'))
        avg = round(avg_data['avg'], 1) if avg_data['avg'] else None
        return Response(success_response({
            'average_rating': avg,
            'total_reviews': reviews.count(),
            'reviews': ReviewSerializer(reviews[:50], many=True).data
        }))


class LeaveReviewView(APIView):
    """Laisser un avis — uniquement après visite GPS confirmée"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Reviews'],
        summary="Laisser un avis",
        description="Uniquement possible après confirmation GPS de la visite.",
        request=CreateReviewSerializer
    )
    def post(self, request, visit_id):
        try:
            visit = VisitRequest.objects.get(
                id=visit_id,
                client=request.user,
                status='completed',
                client_gps_confirmed=True
            )
        except VisitRequest.DoesNotExist:
            return Response(
                error_response("Visite introuvable ou non éligible. GPS requis."),
                status=status.HTTP_404_NOT_FOUND
            )

        if Review.objects.filter(reviewer=request.user, visit_id=visit_id).exists():
            return Response(
                error_response("Vous avez déjà laissé un avis pour cette visite."),
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CreateReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        review = serializer.save(
            reviewer=request.user,
            agent=visit.agent,
            rental_property=visit.visit_property,
            gps_verified=True,
            visit_id=visit_id
        )

        # Mettre à jour le score de fiabilité de l'agent
        if review.agent_rating and hasattr(visit.agent, 'agent_profile'):
            visit.agent.agent_profile.update_reliability_score()

        return Response(
            success_response(ReviewSerializer(review).data, "Avis enregistré ✅"),
            status=status.HTTP_201_CREATED
        )
