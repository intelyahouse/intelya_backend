from django.contrib import admin
from .models import VisitRequest, VisitReview

@admin.register(VisitRequest)
class VisitRequestAdmin(admin.ModelAdmin):
    list_display  = ['client', 'agent', 'get_property', 'status', 'scheduled_date', 'visit_fee', 'payment_status']
    list_filter   = ['status', 'payment_status', 'is_free']
    search_fields = ['client__email', 'agent__email', 'property__title']

    def get_property(self, obj):
        return obj.property.title
    get_property.short_description = 'Bien'

@admin.register(VisitReview)
class VisitReviewAdmin(admin.ModelAdmin):
    list_display    = ['client', 'property_rating', 'agent_rating', 'created_at']
    readonly_fields = ['visit', 'client']