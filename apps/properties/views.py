from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.cache import cache
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from .models import Property, PropertyPhoto, PropertyLike
from .serializers import PropertyListSerializer, PropertyDetailSerializer, PropertyAdminSerializer, CreatePropertySerializer
from apps.agents.models import ClientAgentRelation
from core.permissions import IsAgent, IsAdmin
from core.utils import success_response, error_response
from core.pagination import StandardResultsSetPagination
from core.throttles import SearchThrottle, UploadThrottle
from django.contrib.auth import get_user_model
from rest_framework import generics

User = get_user_model()


class PropertyListView(APIView):
    permission_classes = [AllowAny]
    throttle_classes   = [SearchThrottle]

    @extend_schema(tags=['Properties'], summary="Liste des biens disponibles")
    def get(self, request):
        city         = request.query_params.get('city', '')
        neighborhood = request.query_params.get('neighborhood', '')
        prop_type    = request.query_params.get('type', '')
        min_price    = request.query_params.get('min_price')
        max_price    = request.query_params.get('max_price')
        bedrooms     = request.query_params.get('bedrooms')
        is_furnished = request.query_params.get('furnished')
        has_generator = request.query_params.get('generator')
        has_parking  = request.query_params.get('parking')
        page         = request.query_params.get('page', 1)

        # Cache pour les recherches anonymes
        cache_key = None
        if not request.user.is_authenticated:
            cache_key = f"properties:{city}:{neighborhood}:{prop_type}:{min_price}:{max_price}:{bedrooms}:{page}"
            cached = cache.get(cache_key)
            if cached:
                return Response(success_response(cached))

        # Requête optimisée avec select_related
        queryset = Property.objects.filter(
            status='available'
        ).select_related('agent', 'owner').prefetch_related('photos', 'likes')

        if city:
            queryset = queryset.filter(city__icontains=city)
        if neighborhood:
            queryset = queryset.filter(neighborhood__icontains=neighborhood)
        if prop_type:
            queryset = queryset.filter(property_type=prop_type)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        if bedrooms:
            queryset = queryset.filter(bedrooms=bedrooms)
        if is_furnished == 'true':
            queryset = queryset.filter(is_furnished=True)
        if has_generator == 'true':
            queryset = queryset.filter(has_generator=True)
        if has_parking == 'true':
            queryset = queryset.filter(has_parking=True)

        # Biens de l'agent du client EN PREMIER
        if request.user.is_authenticated and request.user.role in ['client', 'tenant']:
            relation = ClientAgentRelation.objects.filter(
                client=request.user, is_active=True
            ).select_related('agent').first()

            if relation:
                from django.db.models import Case, When, IntegerField, Value
                queryset = queryset.annotate(
                    agent_priority=Case(
                        When(agent=relation.agent, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField()
                    )
                ).order_by('-agent_priority', '-created_at')

        # Pagination
        paginator   = StandardResultsSetPagination()
        page_data   = paginator.paginate_queryset(queryset, request)
        serializer  = PropertyListSerializer(page_data, many=True, context={'request': request})
        result      = paginator.get_paginated_response(serializer.data).data

        if cache_key:
            cache.set(cache_key, result, 300)

        return Response(result)


class PropertyDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=['Properties'], summary="Détail d'un bien")
    def get(self, request, property_id):
        try:
            prop = Property.objects.select_related(
                'agent', 'owner'
            ).prefetch_related('photos', 'likes').get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        # Incrémenter vues (sans bloquer la réponse)
        Property.objects.filter(id=property_id).update(views_count=prop.views_count + 1)

        if request.user.is_authenticated and request.user.role == 'admin':
            serializer = PropertyAdminSerializer(prop, context={'request': request})
        else:
            serializer = PropertyDetailSerializer(prop, context={'request': request})

        return Response(success_response(serializer.data))


class CreatePropertyView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Properties'], summary="Publier un bien (agent)", request=CreatePropertySerializer)
    def post(self, request):
        from apps.agents.models import OwnerAgentRelation
        owner_id = request.data.get('owner_id')
        if not owner_id:
            return Response(error_response("owner_id requis"), status=status.HTTP_400_BAD_REQUEST)

        try:
            owner = User.objects.get(id=owner_id, role='owner')
        except User.DoesNotExist:
            return Response(error_response("Propriétaire introuvable"), status=status.HTTP_404_NOT_FOUND)

        if not OwnerAgentRelation.objects.filter(agent=request.user, owner=owner, status='active').exists():
            return Response(error_response("Ce propriétaire n'est pas lié à votre agence"), status=status.HTTP_403_FORBIDDEN)

        serializer = CreatePropertySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        prop = serializer.save(owner=owner, agent=request.user)

        # Invalider le cache de recherche
        cache.delete_pattern("intelya:properties:*")

        return Response(
            success_response(PropertyDetailSerializer(prop, context={'request': request}).data, "Bien publié ✅"),
            status=status.HTTP_201_CREATED
        )


class UpdatePropertyView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        if request.user.role != 'admin' and prop.agent != request.user:
            return Response(error_response("Non autorisé"), status=status.HTTP_403_FORBIDDEN)

        serializer = CreatePropertySerializer(prop, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        cache.delete_pattern("intelya:properties:*")
        return Response(success_response(serializer.data, "Bien mis à jour"))

    def delete(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        if request.user.role != 'admin' and prop.agent != request.user:
            return Response(error_response("Non autorisé"), status=status.HTTP_403_FORBIDDEN)

        prop.status = 'suspended'
        prop.save(update_fields=['status'])
        cache.delete_pattern("intelya:properties:*")
        return Response(success_response(message="Bien suspendu"))


class PropertyLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        like, created = PropertyLike.objects.get_or_create(property=prop, user=request.user)
        if not created:
            like.delete()
            Property.objects.filter(id=property_id).update(likes_count=max(0, prop.likes_count - 1))
            return Response(success_response(message="Like retiré"))

        Property.objects.filter(id=property_id).update(likes_count=prop.likes_count + 1)
        return Response(success_response(message="Bien liké ❤️"))


class MyFavoritesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        liked = Property.objects.filter(
            likes__user=request.user
        ).select_related('agent', 'owner').prefetch_related('photos')
        paginator  = StandardResultsSetPagination()
        page_data  = paginator.paginate_queryset(liked, request)
        serializer = PropertyListSerializer(page_data, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AgentPropertiesView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    def get(self, request):
        properties = Property.objects.filter(
            agent=request.user
        ).select_related('owner').prefetch_related('photos').order_by('-created_at')
        paginator  = StandardResultsSetPagination()
        page_data  = paginator.paginate_queryset(properties, request)
        serializer = PropertyDetailSerializer(page_data, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class UploadPropertyPhotosView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]
    throttle_classes   = [UploadThrottle]

    def post(self, request, property_id):
        from core.validators import validate_image_file
        try:
            prop = Property.objects.get(id=property_id, agent=request.user)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        photos = request.FILES.getlist('photos')
        if not photos:
            return Response(error_response("Aucune photo"), status=status.HTTP_400_BAD_REQUEST)

        existing_count = prop.photos.count()
        if existing_count + len(photos) > 30:
            return Response(error_response(f"Maximum 30 photos. Vous en avez {existing_count}."), status=status.HTTP_400_BAD_REQUEST)

        # Valider chaque photo
        for photo in photos:
            try:
                validate_image_file(photo)
            except Exception as e:
                return Response(error_response(str(e)), status=status.HTTP_400_BAD_REQUEST)

        from core.compression import compress_image
        created = []
        for i, photo in enumerate(photos):
            # Compresser avant stockage
            compressed_photo = compress_image(photo)
            p = PropertyPhoto.objects.create(
                property=prop, photo=compressed_photo,
                order=existing_count + i,
                is_cover=(existing_count == 0 and i == 0)
            )
            created.append(p)

        return Response(
            success_response({'photos_added': len(created)}, f"{len(created)} photo(s) ajoutée(s)"),
            status=status.HTTP_201_CREATED
        )


class AIMatchView(APIView):
    """Recommandations IA personnalisées pour le client"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.ai_match import get_recommendations_for_user
        from .serializers import PropertyListSerializer

        if request.user.role not in ['client', 'tenant']:
            return Response(
                error_response("Réservé aux clients"),
                status=status.HTTP_403_FORBIDDEN
            )

        recommendations = get_recommendations_for_user(request.user, limit=10)

        result = []
        for rec in recommendations:
            prop = rec['property']
            serializer = PropertyListSerializer(prop, context={'request': request})
            data = serializer.data
            data['ai_match_score'] = rec['score']
            data['ai_match_label'] = (
                "Excellent" if rec['score'] >= 80 else
                "Très bon"  if rec['score'] >= 60 else
                "Bon"       if rec['score'] >= 40 else
                "Possible"
            )
            result.append(data)

        return Response(success_response({
            'total': len(result),
            'recommendations': result
        }))

class FeaturedPropertiesView(generics.ListAPIView):
    """Biens en vedette — les plus récents disponibles"""
    permission_classes = [AllowAny]
    serializer_class   = PropertyListSerializer
    pagination_class   = StandardResultsSetPagination

    def get_queryset(self):
        return Property.objects.filter(
            status='available'
        ).select_related(
            'agent__user', 'owner__user'
        ).prefetch_related('photos').order_by('-created_at')[:6]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'results': serializer.data,
            'count': len(serializer.data),
        })
