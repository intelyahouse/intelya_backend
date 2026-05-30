from django.contrib import admin
from .models import AgentProfile, ClientAgentRelation, OwnerAgentRelation, AgentAvailabilitySlot


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'agency_name', 'certification_level', 'reliability_score', 'working_city', 'total_clients']
    list_filter   = ['certification_level', 'working_city']
    search_fields = ['user__email', 'user__first_name', 'agency_name']
    readonly_fields = ['reliability_score', 'total_reviews', 'total_transactions']

    actions = ['upgrade_to_certified', 'upgrade_to_premium']

    def upgrade_to_certified(self, request, queryset):
        queryset.update(certification_level='certified', max_properties=50)
        self.message_user(request, f"{queryset.count()} agent(s) certifié(s)")
    upgrade_to_certified.short_description = "⭐ Certifier les agents sélectionnés"

    def upgrade_to_premium(self, request, queryset):
        queryset.update(certification_level='premium', max_properties=999)
        self.message_user(request, f"{queryset.count()} agent(s) premium")
    upgrade_to_premium.short_description = "⭐⭐ Passer en Premium"


@admin.register(ClientAgentRelation)
class ClientAgentRelationAdmin(admin.ModelAdmin):
    list_display = ['client', 'agent', 'is_active', 'created_at']
    list_filter  = ['is_active']


@admin.register(OwnerAgentRelation)
class OwnerAgentRelationAdmin(admin.ModelAdmin):
    list_display = ['owner', 'agent', 'status', 'contract_start', 'contract_end']
    list_filter  = ['status']


@admin.register(AgentAvailabilitySlot)
class AgentAvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ['agent', 'day_of_week', 'start_time', 'end_time', 'is_active']
