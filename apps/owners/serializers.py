from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import OwnerProfile
from apps.agents.models import OwnerAgentRelation

User = get_user_model()


class OwnerProfileSerializer(serializers.ModelSerializer):
    full_name     = serializers.CharField(source='user.get_full_name', read_only=True)
    email         = serializers.CharField(source='user.email', read_only=True)
    phone         = serializers.CharField(source='user.phone', read_only=True)
    profile_photo = serializers.ImageField(source='user.profile_photo', read_only=True)
    active_agent  = serializers.SerializerMethodField()

    class Meta:
        model  = OwnerProfile
        fields = [
            'id', 'full_name', 'email', 'phone', 'profile_photo',
            'bio', 'property_count', 'manages_own_tenants',
            'mtn_momo_number', 'orange_money_number',
            'bank_account_number', 'bank_name',
            'land_title_number', 'active_agent', 'created_at'
        ]
        read_only_fields = ['property_count', 'active_agent']

    def get_active_agent(self, obj):
        agent = obj.get_active_agent()
        if agent:
            return {
                'id': str(agent.id),
                'name': agent.get_full_name(),
                'phone': agent.phone,
            }
        return None


class OwnerBankAccountSerializer(serializers.ModelSerializer):
    """Pour mettre à jour uniquement les comptes bancaires"""
    class Meta:
        model  = OwnerProfile
        fields = ['mtn_momo_number', 'orange_money_number', 'bank_account_number', 'bank_name']
