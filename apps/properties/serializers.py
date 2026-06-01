from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Property, PropertyPhoto, PropertyVideo, FloorPlan, PropertyLike

User = get_user_model()


class PropertyPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PropertyPhoto
        fields = ['id', 'photo', 'caption', 'is_cover', 'order']


class PropertyListSerializer(serializers.ModelSerializer):
    """Version allégée pour la liste — sans adresse"""
    cover_photo  = serializers.SerializerMethodField()
    agent_name   = serializers.CharField(source='agent.get_full_name', read_only=True)
    is_liked     = serializers.SerializerMethodField()

    class Meta:
        model  = Property
        fields = [
            'id', 'title', 'property_type', 'status',
            'price', 'payment_period',
            'bedrooms', 'bathrooms', 'area_sqm',
            'city', 'neighborhood',
            'is_furnished', 'is_verified',
            'has_generator', 'has_parking', 'has_borehole',
            'views_count', 'likes_count', 'interested_count',
            'cover_photo', 'agent_name', 'is_liked',
            'created_at'
        ]

    def get_cover_photo(self, obj):
        photo = obj.photos.filter(is_cover=True).first()
        if not photo:
            photo = obj.photos.first()
        if photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(photo.photo.url)
        return None

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Version complète pour le détail — sans adresse complète"""
    photos       = PropertyPhotoSerializer(many=True, read_only=True)
    cover_photo  = serializers.SerializerMethodField()
    agent_name   = serializers.CharField(source='agent.get_full_name', read_only=True)
    # agent_phone masqué — visible uniquement après bail signé
    owner_name   = serializers.CharField(source='owner.get_full_name', read_only=True)
    is_liked     = serializers.SerializerMethodField()
    has_video    = serializers.SerializerMethodField()
    has_floor_plan = serializers.SerializerMethodField()

    class Meta:
        model  = Property
        fields = [
            'id', 'title', 'description', 'property_type', 'status',
            'price', 'payment_period', 'min_lease_months',
            'bedrooms', 'bathrooms', 'living_rooms', 'kitchens',
            'area_sqm', 'floor', 'total_floors', 'is_furnished',
            # Localisation SANS adresse complète
            'city', 'neighborhood',
            # Équipements africains
            'has_generator', 'has_borehole', 'has_water_tank',
            'has_fence', 'has_security_guard', 'has_parking',
            'has_air_conditioning', 'parking_spots',
            # Disponibilité
            'available_from',
            # Stats
            'views_count', 'likes_count', 'interested_count',
            'is_verified',
            # Photos et médias
            'photos', 'cover_photo', 'has_video', 'has_floor_plan',
            # Agent et propriétaire
            'agent_name', 'owner_name',
            'is_liked', 'created_at'
        ]

    def get_cover_photo(self, obj):
        photo = obj.photos.filter(is_cover=True).first() or obj.photos.first()
        if photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(photo.photo.url)
        return None

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_has_video(self, obj):
        return hasattr(obj, 'video') and obj.video is not None

    def get_has_floor_plan(self, obj):
        return hasattr(obj, 'floor_plan') and obj.floor_plan is not None


class PropertyAdminSerializer(PropertyDetailSerializer):
    """Version admin — avec adresse complète"""
    class Meta(PropertyDetailSerializer.Meta):
        fields = PropertyDetailSerializer.Meta.fields + ['full_address']


class CreatePropertySerializer(serializers.ModelSerializer):
    """Pour créer ou modifier un bien — réservé aux agents"""
    class Meta:
        model  = Property
        fields = [
            'title', 'description', 'property_type',
            'price', 'payment_period', 'min_lease_months',
            'bedrooms', 'bathrooms', 'living_rooms', 'kitchens',
            'area_sqm', 'floor', 'total_floors', 'is_furnished',
            'full_address', 'city', 'neighborhood',
            'has_generator', 'has_borehole', 'has_water_tank',
            'has_fence', 'has_security_guard', 'has_parking',
            'has_air_conditioning', 'parking_spots',
            'available_from', 'min_lease_months',
        ]

    def validate_description(self, value):
        if len(value.split()) < 50:
            raise serializers.ValidationError("La description doit contenir au minimum 50 mots.")
        return value
