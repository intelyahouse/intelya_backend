from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from .models import Property, PropertyPhoto, PropertyLike
from .serializers import (
    PropertyListSerializer, PropertyDetailSerializer,
    PropertyAdminSerializer, CreatePropertySerializer
)
from apps.agents.models import ClientAgentRelation
from core.permissions import IsAgent, IsAdmin
from core.utils import success_response, error_response

User = get_user_model()


class PropertyListView(APIView):
    """
    Liste des biens avec filtrage intelligent.
    - Les biens de l'agent du client apparaissent EN PREMIER
    - Jamais d'adresse complète pour les clients
    """
    permission_classes = [AllowAny]

    @extend_schema(tags=['Properties'], summary="Liste des biens disponibles")
    def get(self, request):
        queryset = Property.objects.filter(
            status='available'
        ).select_related('agent', 'owner').prefetch_related('photos')

        # ===== FILTRES =====
        city         = request.query_params.get('city', '')
        neighborhood = request.query_params.get('neighborhood', '')
        prop_type    = request.query_params.get('type', '')
        min_price    = request.query_params.get('min_price')
        max_price    = request.query_params.get('max_price')
        bedrooms     = request.query_params.get('bedrooms')
        is_furnished = request.query_params.get('furnished')
        has_generator = request.query_params.get('generator')
        has_parking  = request.query_params.get('parking')
        has_borehole = request.query_params.get('borehole')

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
        if has_borehole == 'true':
            queryset = queryset.filter(has_borehole=True)

        # ===== LOGIQUE AGENT DU CLIENT EN PREMIER =====
        if request.user.is_authenticated and request.user.role in ['client', 'tenant']:
            relation = ClientAgentRelation.objects.filter(
                client=request.user, is_active=True
            ).first()

            if relation:
                # Biens de l'agent du client EN PREMIER
                agent_properties   = queryset.filter(agent=relation.agent)
                other_properties   = queryset.exclude(agent=relation.agent)
                combined = list(agent_properties) + list(other_properties)
                serializer = PropertyListSerializer(
                    combined, many=True, context={'request': request}
                )
                return Response(success_response(serializer.data))

        serializer = PropertyListSerializer(queryset, many=True, context={'request': request})
        return Response(success_response(serializer.data))


class PropertyDetailView(APIView):
    """Détail d'un bien — sans adresse complète"""
    permission_classes = [AllowAny]

    @extend_schema(tags=['Properties'], summary="Détail d'un bien")
    def get(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(
                error_response("Bien introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )

        prop.views_count += 1
        prop.save(update_fields=['views_count'])

        # Admin voit l'adresse complète
        if request.user.is_authenticated and request.user.role == 'admin':
            serializer = PropertyAdminSerializer(prop, context={'request': request})
        else:
            serializer = PropertyDetailSerializer(prop, context={'request': request})

        return Response(success_response(serializer.data))


class CreatePropertyView(APIView):
    """Créer un bien — réservé aux agents"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Properties'],
        summary="Publier un bien (agent uniquement)",
        request=CreatePropertySerializer
    )
    def post(self, request):
        owner_id = request.data.get('owner_id')
        if not owner_id:
            return Response(
                error_response("owner_id est requis"),
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            owner = User.objects.get(id=owner_id, role='owner')
        except User.DoesNotExist:
            return Response(
                error_response("Propriétaire introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )

        # Vérifier que l'agent gère bien ce propriétaire
        from apps.agents.models import OwnerAgentRelation
        if not OwnerAgentRelation.objects.filter(
            agent=request.user, owner=owner, status='active'
        ).exists():
            return Response(
                error_response("Ce propriétaire n'est pas lié à votre agence"),
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CreatePropertySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = serializer.save(owner=owner, agent=request.user)
        return Response(
            success_response(
                PropertyDetailSerializer(prop, context={'request': request}).data,
                "Bien publié avec succès"
            ),
            status=status.HTTP_201_CREATED
        )


class UpdatePropertyView(APIView):
    """Modifier ou supprimer un bien"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Properties'], summary="Modifier un bien")
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
        return Response(success_response(serializer.data, "Bien mis à jour"))

    @extend_schema(tags=['Properties'], summary="Supprimer/Suspendre un bien")
    def delete(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        if request.user.role != 'admin' and prop.agent != request.user:
            return Response(error_response("Non autorisé"), status=status.HTTP_403_FORBIDDEN)

        prop.status = 'suspended'
        prop.save(update_fields=['status'])
        return Response(success_response(message="Bien suspendu"))


class PropertyLikeView(APIView):
    """Liker ou unliker un bien"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Properties'], summary="Liker ou unliker un bien")
    def post(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        like, created = PropertyLike.objects.get_or_create(
            property=prop, user=request.user
        )

        if not created:
            like.delete()
            prop.likes_count = max(0, prop.likes_count - 1)
            prop.save(update_fields=['likes_count'])
            return Response(success_response(message="Like retiré"))

        prop.likes_count += 1
        prop.save(update_fields=['likes_count'])
        return Response(success_response(message="Bien liké ❤️"))


class MyFavoritesView(APIView):
    """Mes biens favoris"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Properties'], summary="Mes biens favoris")
    def get(self, request):
        liked = Property.objects.filter(
            likes__user=request.user
        ).select_related('agent', 'owner').prefetch_related('photos')
        serializer = PropertyListSerializer(liked, many=True, context={'request': request})
        return Response(success_response(serializer.data))


class AgentPropertiesView(APIView):
    """Biens gérés par l'agent connecté"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Properties'], summary="Mes biens gérés")
    def get(self, request):
        properties = Property.objects.filter(
            agent=request.user
        ).select_related('owner').prefetch_related('photos')
        serializer = PropertyDetailSerializer(properties, many=True, context={'request': request})
        return Response(success_response(serializer.data))


class UploadPropertyPhotosView(APIView):
    """Upload photos pour un bien"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Properties'], summary="Uploader des photos")
    def post(self, request, property_id):
        try:
            prop = Property.objects.get(id=property_id, agent=request.user)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        photos = request.FILES.getlist('photos')
        if not photos:
            return Response(error_response("Aucune photo fournie"), status=status.HTTP_400_BAD_REQUEST)

        existing_count = prop.photos.count()
        if existing_count + len(photos) > 30:
            return Response(
                error_response(f"Maximum 30 photos. Vous en avez déjà {existing_count}."),
                status=status.HTTP_400_BAD_REQUEST
            )

        created_photos = []
        for i, photo in enumerate(photos):
            p = PropertyPhoto.objects.create(
                property=prop,
                photo=photo,
                order=existing_count + i,
                is_cover=(existing_count == 0 and i == 0)
            )
            created_photos.append(p)

        return Response(
            success_response(
                {'photos_added': len(created_photos)},
                f"{len(created_photos)} photo(s) ajoutée(s)"
            ),
            status=status.HTTP_201_CREATED
        )
