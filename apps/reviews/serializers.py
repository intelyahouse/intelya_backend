from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name   = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    property_title  = serializers.CharField(source='rental_property.title', read_only=True)
    reviewer_photo  = serializers.ImageField(source='reviewer.profile_photo', read_only=True)

    class Meta:
        model  = Review
        fields = [
            'id', 'reviewer_name', 'reviewer_photo',
            'property_title', 'agent_rating', 'agent_comment',
            'property_rating', 'property_comment',
            'gps_verified', 'created_at'
        ]


class CreateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Review
        fields = ['agent_rating', 'agent_comment', 'property_rating', 'property_comment']

    def validate_agent_rating(self, value):
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("Note entre 1 et 5")
        return value

    def validate_property_rating(self, value):
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("Note entre 1 et 5")
        return value
