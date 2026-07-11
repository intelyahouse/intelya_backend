from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ['reviewer', 'agent', 'rental_property', 'agent_rating', 'property_rating', 'gps_verified', 'created_at']
    list_filter   = ['gps_verified', 'agent_rating', 'property_rating']
    search_fields = ['reviewer__email']
    readonly_fields = ['reviewer', 'agent', 'rental_property', 'visit_id']
