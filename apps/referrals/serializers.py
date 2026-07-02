from rest_framework import serializers
from .models import Referral


class ReferralSerializer(serializers.ModelSerializer):
    referrer_name = serializers.CharField(source='referrer.get_full_name', read_only=True)
    referred_name = serializers.CharField(source='referred.get_full_name', read_only=True)

    class Meta:
        model  = Referral
        fields = ['id', 'referrer_name', 'referred_name', 'status', 'bonus_amount', 'rewarded_at', 'created_at']
