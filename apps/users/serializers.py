from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import OTPVerification, Blacklist
from core.validators import validate_phone_cameroon
import random
import string

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email',
            'phone', 'password', 'confirm_password', 'language'
        ]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value.lower()

    def validate_phone(self, value):
        try:
            validate_phone_cameroon(value)
        except Exception as e:
            from rest_framework import serializers as ser
            raise ser.ValidationError(str(e))
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Ce téléphone est déjà utilisé.")
        if Blacklist.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Ce numéro est bloqué.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        if not data.get('first_name'):
            raise serializers.ValidationError("Le prénom est obligatoire.")
        if not data.get('last_name'):
            raise serializers.ValidationError("Le nom est obligatoire.")
        return data

    def validate_first_name(self, value):
        if '<' in value or '>' in value or 'script' in value.lower():
            from rest_framework import serializers
            raise serializers.ValidationError("Caractères non autorisés.")
        return value.strip()

    def validate_last_name(self, value):
        if '<' in value or '>' in value or 'script' in value.lower():
            from rest_framework import serializers
            raise serializers.ValidationError("Caractères non autorisés.")
        return value.strip()

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        referral_code = self._generate_referral_code()
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data['phone'],
            language=validated_data.get('language', 'fr'),
            referral_code=referral_code,
            role='client',
        )
        return user

    def _generate_referral_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=8))
            if not User.objects.filter(referral_code=code).exists():
                return code


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6, min_length=6)


class OTPResendSerializer(serializers.Serializer):
    phone = serializers.CharField()


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'first_name', 'last_name',
            'full_name', 'role', 'profile_photo', 'is_validated',
            'is_phone_verified', 'is_blocked', 'validation_status',
            'referral_code', 'language', 'date_joined'
        ]
        read_only_fields = [
            'id', 'role', 'is_validated', 'is_phone_verified',
            'is_blocked', 'validation_status', 'referral_code', 'date_joined'
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField()

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return data


class RoleRequestSerializer(serializers.Serializer):
    ROLE_CHOICES = [('agent', 'Agent'), ('owner', 'Propriétaire')]
    requested_role = serializers.ChoiceField(choices=ROLE_CHOICES)
    cni_number = serializers.CharField(max_length=50)
    cni_front_photo = serializers.ImageField()
    cni_back_photo = serializers.ImageField()
    selfie_photo = serializers.ImageField()

    def validate_cni_number(self, value):
        if Blacklist.objects.filter(cni_number=value).exists():
            raise serializers.ValidationError("Cette CNI est blacklistée.")
        user = self.context['request'].user
        if User.objects.filter(cni_number=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Cette CNI est déjà utilisée.")
        return value
