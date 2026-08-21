from django.contrib import admin
from .models import AgentOwnerContract, LeaseContract


@admin.register(AgentOwnerContract)
class AgentOwnerContractAdmin(admin.ModelAdmin):
    list_display = ['agent', 'owner', 'agency', 'status', 'commission_percent', 'start_date', 'end_date']
    list_filter  = ['status']
    search_fields = ['agent__email', 'owner__email']


@admin.register(LeaseContract)
class LeaseContractAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'owner', 'agent', 'rental_property', 'status', 'monthly_rent', 'start_date', 'end_date']
    list_filter  = ['status', 'commission_paid']
    search_fields = ['tenant__email', 'owner__email']
