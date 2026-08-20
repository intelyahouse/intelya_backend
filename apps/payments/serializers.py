from rest_framework import serializers
from .models import Transaction, Escrow


class TransactionSerializer(serializers.ModelSerializer):
    payer_id      = serializers.CharField(source='payer.id', read_only=True)
    payer_name    = serializers.CharField(source='payer.get_full_name', read_only=True)
    receiver_id   = serializers.CharField(source='receiver.id', read_only=True)
    receiver_name = serializers.CharField(source='receiver.get_full_name', read_only=True)

    class Meta:
        model  = Transaction
        fields = [
            'id', 'reference', 'payer_id', 'payer_name', 'receiver_id', 'receiver_name',
            'transaction_type', 'amount', 'platform_fee', 'agency_fee_amount',
            'net_amount', 'currency', 'status', 'payment_method',
            'description', 'completed_at', 'created_at'
        ]


class InitiatePaymentSerializer(serializers.Serializer):
    METHOD_CHOICES = [('mtn', 'MTN Mobile Money'), ('orange', 'Orange Money'), ('bank', 'Compte bancaire')]
    amount         = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=METHOD_CHOICES)
    phone_number   = serializers.CharField(required=False)
    related_type   = serializers.ChoiceField(choices=[('visit', 'Visite'), ('rent', 'Loyer'), ('commission', 'Commission')])
    related_id     = serializers.UUIDField()
    months         = serializers.IntegerField(required=False, min_value=1, default=1)


class WebhookPayloadSerializer(serializers.Serializer):
    reference  = serializers.CharField()
    status     = serializers.CharField()
    amount     = serializers.CharField(required=False)
    operator   = serializers.CharField(required=False)