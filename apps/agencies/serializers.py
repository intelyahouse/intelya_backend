from rest_framework import serializers
from .models import Agency, AgencyInvitation


class AgencyMemberSerializer(serializers.Serializer):
    id        = serializers.UUIDField(source="user.id")
    full_name = serializers.CharField(source="user.get_full_name")
    email     = serializers.EmailField(source="user.email")
    is_gerant = serializers.SerializerMethodField()

    def get_is_gerant(self, obj):
        agency = self.context.get("agency")
        return bool(agency and obj.user_id == agency.owner_agent_id)


class AgencySerializer(serializers.ModelSerializer):
    owner_agent_id   = serializers.UUIDField(source="owner_agent.id", read_only=True)
    owner_agent_name = serializers.CharField(source="owner_agent.get_full_name", read_only=True)
    members          = serializers.SerializerMethodField()
    member_count     = serializers.SerializerMethodField()

    class Meta:
        model  = Agency
        fields = [
            'id', 'name', 'is_solo', 'owner_agent_id', 'owner_agent_name',
            'members', 'member_count', 'created_at',
            'mtn_momo_number', 'orange_money_number', 'bank_account_number', 'bank_name',
            'reliability_score', 'total_reviews', 'disputes_confirmed_against',
        ]

    def get_members(self, obj):
        agents = obj.agents.select_related('user').all()
        return AgencyMemberSerializer(agents, many=True, context={'agency': obj}).data

    def get_member_count(self, obj):
        return obj.agents.count()


class AgencyPaymentInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Agency
        fields = ['mtn_momo_number', 'orange_money_number', 'bank_account_number', 'bank_name']


class AgencyInvitationSerializer(serializers.ModelSerializer):
    agency_id     = serializers.UUIDField(source="agency.id", read_only=True)
    agency_name   = serializers.CharField(source="agency.name", read_only=True)
    invited_name  = serializers.CharField(source="invited_user.get_full_name", read_only=True)
    invited_by_name = serializers.CharField(source="invited_by.get_full_name", read_only=True)

    class Meta:
        model  = AgencyInvitation
        fields = [
            'id', 'agency_id', 'agency_name', 'invited_name', 'invited_by_name',
            'status', 'created_at', 'responded_at',
        ]
