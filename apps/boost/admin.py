from django.contrib import admin
from .models import Boost


@admin.register(Boost)
class BoostAdmin(admin.ModelAdmin):
    list_display = ['agent', 'level', 'duration_days', 'target_city', 'is_active', 'start_date', 'end_date']
    list_filter  = ['level', 'is_active', 'target_city']
    search_fields = ['agent__email', 'agent__first_name']
