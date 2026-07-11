from django.contrib import admin
from .models import RentPayment, DebtRecord, Complaint


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'amount', 'status', 'due_date', 'paid_at', 'period_month', 'period_year']
    list_filter  = ['status', 'payment_method']
    search_fields = ['tenant__email']


@admin.register(DebtRecord)
class DebtRecordAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'amount_owed', 'action_taken', 'new_due_date', 'created_at']
    list_filter  = ['action_taken']


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'category', 'title', 'status', 'created_at']
    list_filter  = ['status', 'category']
