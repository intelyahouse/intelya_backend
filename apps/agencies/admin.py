from django.contrib import admin
from .models import Agency


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display  = ["name", "owner_agent", "is_solo", "created_at"]
    list_filter   = ["is_solo"]
    search_fields = ["name", "owner_agent__email", "owner_agent__first_name"]
