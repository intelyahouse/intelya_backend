from rest_framework import serializers
from .models import AgentOwnerContract, LeaseContract
from django.contrib.auth import get_user_model

User = get_user_model()


class AgentOwnerContractSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True, default=None)

    class Meta:
        model  = AgentOwnerContract
        fields = [
            'id', 'agent_name', 'owner_name', 'agency_name', 'status',
            'commission_percent', 'start_date', 'end_date',
            'terms', 'signed_by_agent', 'signed_by_owner',
            'signed_at', 'created_at'
        ]
        read_only_fields = ['signed_by_agent', 'signed_by_owner', 'signed_at', 'status']


class CreateAgentOwnerContractSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgentOwnerContract
        fields = ['owner', 'commission_percent', 'start_date', 'end_date', 'terms']


class CreateLeaseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaseContract
        fields = [
            'tenant', 'owner', 'rental_property',
            'monthly_rent', 'deposit_amount',
            'agent_commission', 'commission_before_rent',
            'start_date', 'end_date', 'payment_day'
        ]


class LeaseContractSerializer(serializers.ModelSerializer):
    tenant_name   = serializers.CharField(source='tenant.get_full_name', read_only=True)
    owner_name    = serializers.CharField(source='owner.get_full_name', read_only=True)
    agent_name    = serializers.CharField(source='agent.get_full_name', read_only=True)
    property_title = serializers.CharField(source='rental_property.title', read_only=True)
    renewal_date  = serializers.SerializerMethodField()

    class Meta:
        model  = LeaseContract
        fields = [
            'id', 'tenant_name', 'owner_name', 'agent_name',
            'property_title', 'status',
            'monthly_rent', 'deposit_amount',
            'platform_fee_percent', 'agent_commission',
            'commission_paid', 'commission_before_rent',
            'start_date', 'end_date', 'payment_day',
            'signed_by_tenant', 'signed_by_owner', 'signed_at',
            'renewal_date', 'created_at'
        ]

    def get_renewal_date(self, obj):
        return obj.get_renewal_notification_date()
