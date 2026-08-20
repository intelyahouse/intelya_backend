from django.contrib import admin
from .models import Transaction, Escrow, PaymentSplitEntry, RentFeeTier


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ['reference', 'payer', 'receiver', 'transaction_type', 'amount', 'status', 'payment_method', 'created_at']
    list_filter   = ['status', 'transaction_type', 'payment_method']
    search_fields = ['reference', 'payer__email', 'receiver__email']
    readonly_fields = ['reference', 'webhook_data', 'external_reference']


@admin.register(Escrow)
class EscrowAdmin(admin.ModelAdmin):
    list_display = ['transaction', 'amount', 'status', 'held_for', 'release_after']
    list_filter  = ['status']


@admin.register(PaymentSplitEntry)
class PaymentSplitEntryAdmin(admin.ModelAdmin):
    list_display  = ['transaction', 'agency', 'amount', 'status', 'created_at']
    list_filter   = ['status']
    search_fields = ['agency__name', 'transaction__reference']


@admin.register(RentFeeTier)
class RentFeeTierAdmin(admin.ModelAdmin):
    list_display = ['min_rent', 'max_rent', 'fee_amount', 'is_active']
    list_filter  = ['is_active']
    ordering     = ['min_rent']
