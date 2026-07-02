from rest_framework import serializers
from .models import Boost


class BoostSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Boost
        fields = [
            'id', 'agent_name', 'level', 'duration_days',
            'target_city', 'target_neighborhood',
            'price_paid', 'is_active', 'start_date', 'end_date',
            'is_expired', 'created_at'
        ]


class CreateBoostSerializer(serializers.Serializer):
    LEVEL_CHOICES    = [('bronze', 'Bronze'), ('silver', 'Argent'), ('gold', 'Or')]
    DURATION_CHOICES = [(7, '7 jours'), (15, '15 jours'), (30, '30 jours')]

    level        = serializers.ChoiceField(choices=LEVEL_CHOICES)
    duration_days = serializers.ChoiceField(choices=DURATION_CHOICES)
    target_city  = serializers.CharField(max_length=100)
    target_neighborhood = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=[('mtn', 'MTN'), ('orange', 'Orange'), ('bank', 'Banque')]
    )
    phone_number = serializers.CharField(required=False)
