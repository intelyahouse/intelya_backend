from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import AgentProfile, ClientAgentRelation, OwnerAgentRelation, AgentAvailabilitySlot

User = get_user_model()


class AgentProfileSerializer(serializers.ModelSerializer):
    full_name   = serializers.CharField(source='user.get_full_name', read_only=True)
    email       = serializers.CharField(source='user.email', read_only=True)
    phone       = serializers.CharField(source='user.phone', read_only=True)
    profile_photo = serializers.ImageField(source='user.profile_photo', read_only=True)
    agency      = serializers.SerializerMethodField()

    class Meta:
        model  = AgentProfile
        fields = [
            'id', 'full_name', 'email', 'phone', 'profile_photo',
            'agency_name', 'agency', 'bio', 'certification_level',
            'working_city', 'working_zones',
            'commission_type', 'commission_value',
            'visit_fee', 'visit_fee_is_free',
            'commission_before_rent',
            'reliability_score', 'total_reviews',
            'response_rate', 'total_transactions',
            'total_clients', 'total_properties',
            'mtn_momo_number', 'orange_money_number',
            'debt_grace_days', 'notifications_enabled',
        ]
        read_only_fields = [
            'reliability_score', 'total_reviews', 'response_rate',
            'total_transactions', 'total_clients', 'total_properties',
            'certification_level'
        ]

    def get_agency(self, obj):
        return {"id": str(obj.agency_id), "name": obj.agency.name} if obj.agency_id else None


class PublicAgentSerializer(serializers.ModelSerializer):
    """Vue publique de l'agent — pour les clients et propriétaires sans agent"""
    full_name     = serializers.CharField(source='user.get_full_name', read_only=True)
    profile_photo = serializers.SerializerMethodField()
    has_active_boost = serializers.SerializerMethodField()
    agency        = serializers.SerializerMethodField()

    class Meta:
        model  = AgentProfile
        fields = [
            'id', 'full_name', 'profile_photo',
            'agency_name', 'agency', 'bio', 'certification_level',
            'working_city', 'reliability_score', 'total_reviews',
            'visit_fee_is_free', 'visit_fee',
            'total_transactions', 'has_active_boost'
        ]

    def get_agency(self, obj):
        return {"id": str(obj.agency_id), "name": obj.agency.name} if obj.agency_id else None

    def get_profile_photo(self, obj):
        photo = obj.user.profile_photo
        if not photo:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(photo.url) if request else photo.url

    def get_has_active_boost(self, obj):
        return obj.user.boosts.filter(is_active=True).exists() if hasattr(obj.user, 'boosts') else False


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model  = AgentAvailabilitySlot
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'is_active']


class ClientAgentRelationSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.get_full_name', read_only=True)
    agent_name  = serializers.CharField(source='agent.get_full_name', read_only=True)

    class Meta:
        model  = ClientAgentRelation
        fields = ['id', 'client_name', 'agent_name', 'is_active', 'created_at']
