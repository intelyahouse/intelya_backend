from rest_framework import serializers
from .models import Dispute, Report


class DisputeSerializer(serializers.ModelSerializer):
    claimant_name  = serializers.CharField(source='claimant.get_full_name', read_only=True)
    defendant_name = serializers.CharField(source='defendant.get_full_name', read_only=True)
    agency_name    = serializers.CharField(source='agency.name', read_only=True, default=None)

    class Meta:
        model  = Dispute
        fields = [
            'id', 'claimant_name', 'defendant_name', 'agency_name',
            'dispute_type', 'status', 'title', 'description',
            'evidence', 'defendant_response',
            'decision', 'decision_note', 'decided_at',
            'created_at'
        ]
        read_only_fields = ['status', 'decision', 'decision_note', 'decided_at']


class CreateDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Dispute
        fields = ['defendant', 'dispute_type', 'title', 'description', 'evidence', 'related_visit_id', 'related_payment_id']


class DisputeResponseSerializer(serializers.Serializer):
    response = serializers.CharField()


class ReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.get_full_name', read_only=True)
    reported_name = serializers.CharField(source='reported.get_full_name', read_only=True)

    class Meta:
        model  = Report
        fields = ['id', 'reporter_name', 'reported_name', 'reason', 'description', 'status', 'created_at']
        read_only_fields = ['status']


class CreateReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Report
        fields = ['reported', 'reason', 'description']
