from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import OwnerProfile, BankAccount, PaymentPreferences
from apps.agents.models import OwnerAgentRelation

User = get_user_model()


class OwnerProfileSerializer(serializers.ModelSerializer):
    full_name     = serializers.CharField(source='user.get_full_name', read_only=True)
    email         = serializers.CharField(source='user.email', read_only=True)
    phone         = serializers.CharField(source='user.phone', read_only=True)
    profile_photo = serializers.ImageField(source='user.profile_photo', read_only=True)
    active_agent  = serializers.SerializerMethodField()

    class Meta:
        model  = OwnerProfile
        fields = [
            'id', 'full_name', 'email', 'phone', 'profile_photo',
            'bio', 'property_count', 'manages_own_tenants',
            'mtn_momo_number', 'orange_money_number',
            'bank_account_number', 'bank_name',
            'land_title_number', 'active_agent', 'created_at'
        ]
        read_only_fields = ['property_count', 'active_agent']

    def get_active_agent(self, obj):
        agent = obj.get_active_agent()
        if agent:
            return {
                'id': str(agent.id),
                'name': agent.get_full_name(),
                'phone': agent.phone,
            }
        return None


class OwnerBankAccountSerializer(serializers.ModelSerializer):
    """Pour mettre à jour uniquement les comptes bancaires du modèle OwnerProfile (legacy)"""
    class Meta:
        model  = OwnerProfile
        fields = ['mtn_momo_number', 'orange_money_number', 'bank_account_number', 'bank_name']


class BankAccountSerializer(serializers.ModelSerializer):
    """CRUD complet pour le modèle BankAccount"""
    
    class Meta:
        model = BankAccount
        fields = [
            'id', 'account_type', 'account_number', 'account_name',
            'bank_name', 'is_default', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_account_number(self, value):
        """Valider le numéro de compte"""
        if not value or len(value.replace(' ', '')) < 10:
            raise serializers.ValidationError(
                "Le numéro de compte doit contenir au minimum 10 caractères"
            )
        return value

    def create(self, validated_data):
        """Créer un nouveau compte bancaire"""
        owner = self.context['owner']
        validated_data['owner'] = owner
        return super().create(validated_data)


class PaymentPreferencesSerializer(serializers.ModelSerializer):
    """CRUD pour les préférences de paiement"""
    
    class Meta:
        model = PaymentPreferences
        fields = [
            'id', 'payout_frequency', 'minimum_payout_amount',
            'preferred_bank_account', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_minimum_payout_amount(self, value):
        """Valider le montant minimum de payout"""
        if value < 0:
            raise serializers.ValidationError(
                "Le montant minimum de payout ne peut pas être négatif"
            )
        if value > 9999999.99:
            raise serializers.ValidationError(
                "Le montant minimum de payout dépasse la limite autorisée"
            )
        return value

    def create(self, validated_data):
        """Créer les préférences de paiement"""
        owner = self.context['owner']
        validated_data['owner'] = owner
        return super().create(validated_data)

    def validate_preferred_bank_account(self, value):
        """Vérifier que le compte bancaire appartient au propriétaire"""
        if value:
            owner = self.context.get('owner')
            if value.owner != owner:
                raise serializers.ValidationError(
                    "Ce compte bancaire n'appartient pas à ce propriétaire"
                )
        return value
