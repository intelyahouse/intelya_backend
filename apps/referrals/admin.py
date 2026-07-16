from django.contrib import admin
from .models import Referral


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referred', 'status', 'bonus_amount', 'rewarded_at']
    list_filter  = ['status']
