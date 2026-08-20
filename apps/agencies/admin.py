from django.contrib import admin
from .models import Agency, AgencyInvitation


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display  = ["name", "owner_agent", "is_solo", "reliability_score", "total_reviews", "disputes_confirmed_against", "created_at"]
    list_filter   = ["is_solo"]
    readonly_fields = ["reliability_score", "total_reviews", "disputes_confirmed_against"]
    search_fields = ["name", "owner_agent__email", "owner_agent__first_name"]


@admin.register(AgencyInvitation)
class AgencyInvitationAdmin(admin.ModelAdmin):
    list_display  = ["agency", "invited_user", "invited_by", "status", "created_at"]
    list_filter   = ["status"]
    search_fields = ["agency__name", "invited_user__email", "invited_by__email"]
