from rest_framework import serializers
from .models import VisitRequest, VisitReview


class VisitRequestSerializer(serializers.ModelSerializer):
    client_name          = serializers.CharField(source='client.get_full_name', read_only=True)
    agent_name           = serializers.CharField(source='agent.get_full_name', read_only=True)
    property_title       = serializers.CharField(source='rental_property.title', read_only=True)
    property_city        = serializers.CharField(source='rental_property.city', read_only=True)
    property_neighborhood = serializers.CharField(source='rental_property.neighborhood', read_only=True)

    class Meta:
        model  = VisitRequest
        fields = [
            'id', 'client_name', 'agent_name',
            'property_title', 'property_city', 'property_neighborhood',
            'status', 'scheduled_date', 'scheduled_time',
            'visit_fee', 'is_free', 'payment_status',
            'client_gps_confirmed', 'agent_confirmed',
            'client_message', 'cancellation_reason', 'created_at'
        ]


class CreateVisitSerializer(serializers.Serializer):
    property_id    = serializers.UUIDField()
    client_message = serializers.CharField(required=False, allow_blank=True)


class ScheduleVisitSerializer(serializers.Serializer):
    scheduled_date = serializers.DateField()
    scheduled_time = serializers.TimeField()


class GPSConfirmSerializer(serializers.Serializer):
    latitude  = serializers.FloatField()
    longitude = serializers.FloatField()


class CancelVisitSerializer(serializers.Serializer):
    reason = serializers.CharField()


class VisitReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VisitReview
        fields = [
            'id', 'property_rating', 'property_comment',
            'agent_rating', 'agent_comment', 'created_at'
        ]

    def validate_property_rating(self, value):
        if value and not (1 <= value <= 5):
            raise serializers.ValidationError("Note entre 1 et 5")
        return value

    def validate_agent_rating(self, value):
        if value and not (1 <= value <= 5):
            raise serializers.ValidationError("Note entre 1 et 5")
        return value
