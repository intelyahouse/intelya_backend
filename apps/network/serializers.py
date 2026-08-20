from rest_framework import serializers
from .models import Collaboration, CollaborationProposal


class NetworkAgencySerializer(serializers.Serializer):
    """Vue publique (reseau professionnel) d'une agence -- pas de details internes."""
    id           = serializers.UUIDField()
    name         = serializers.CharField()
    member_count = serializers.IntegerField()
    is_solo      = serializers.BooleanField()


class CollaborationProposalSerializer(serializers.ModelSerializer):
    proposed_by_name   = serializers.CharField(source='proposed_by.get_full_name', read_only=True)
    proposed_by_agency_name = serializers.CharField(source='proposed_by_agency.name', read_only=True)

    class Meta:
        model  = CollaborationProposal
        fields = [
            'id', 'proposed_by_name', 'proposed_by_agency_name',
            'client_agency_amount', 'property_agency_amount', 'total_amount',
            'created_at',
        ]


class CollaborationSerializer(serializers.ModelSerializer):
    property_title      = serializers.CharField(source='property.title', read_only=True)
    property_id_str      = serializers.CharField(source='property.id', read_only=True)
    client_name          = serializers.SerializerMethodField()
    client_agency_name   = serializers.CharField(source='client_agency.name', read_only=True)
    property_agency_name = serializers.CharField(source='property_agency.name', read_only=True)
    initiated_by_name    = serializers.CharField(source='initiated_by.get_full_name', read_only=True)
    last_proposed_by_agency_name = serializers.CharField(source='last_proposed_by_agency.name', read_only=True)
    responded_by_name    = serializers.CharField(source='responded_by.get_full_name', read_only=True)
    proposals            = CollaborationProposalSerializer(many=True, read_only=True)

    class Meta:
        model  = Collaboration
        fields = [
            'id', 'property_id_str', 'property_title', 'client_name',
            'client_agency_name', 'property_agency_name', 'initiated_by_name',
            'client_agency_amount', 'property_agency_amount', 'total_amount',
            'status', 'last_proposed_by_agency_name',
            'responded_by_name', 'responded_at',
            'commission_disbursed', 'commission_disbursed_at',
            'created_at', 'updated_at', 'proposals',
        ]

    def get_client_name(self, obj):
        return obj.client.get_full_name() if obj.client else None
