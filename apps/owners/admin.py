from django.contrib import admin
from .models import OwnerProfile


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'property_count', 'manages_own_tenants', 'has_payment_method']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']

    def has_payment_method(self, obj):
        return bool(obj.mtn_momo_number or obj.orange_money_number or obj.bank_account_number)
    has_payment_method.boolean = True
    has_payment_method.short_description = 'Compte bancaire'
