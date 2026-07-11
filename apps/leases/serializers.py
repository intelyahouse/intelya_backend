from rest_framework import serializers
from .models import RentPayment, DebtRecord, Complaint


class RentPaymentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)

    class Meta:
        model  = RentPayment
        fields = [
            'id', 'tenant_name', 'amount', 'platform_fee',
            'owner_amount', 'status', 'payment_method',
            'payment_reference', 'due_date', 'paid_at',
            'confirmed_by_agent', 'period_month', 'period_year',
            'created_at'
        ]
        read_only_fields = ['platform_fee', 'owner_amount', 'status']


class ConfirmCashPaymentSerializer(serializers.Serializer):
    rent_payment_id = serializers.UUIDField()
    notes           = serializers.CharField(required=False, allow_blank=True)


class DebtActionSerializer(serializers.Serializer):
    ACTION_CHOICES = [('extend', 'Prolonger'), ('claim', 'Réclamer')]
    action       = serializers.ChoiceField(choices=ACTION_CHOICES)
    new_due_date = serializers.DateField(required=False)
    notes        = serializers.CharField(required=False, allow_blank=True)


class ComplaintSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.get_full_name', read_only=True)

    class Meta:
        model  = Complaint
        fields = [
            'id', 'tenant_name', 'category', 'title',
            'description', 'status', 'resolution_note',
            'resolved_at', 'created_at'
        ]
        read_only_fields = ['status', 'resolution_note', 'resolved_at']


class CreateComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Complaint
        fields = ['category', 'title', 'description']
