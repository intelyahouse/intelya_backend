from django.contrib import admin
from .models import Collaboration, CollaborationProposal


class CollaborationProposalInline(admin.TabularInline):
    model = CollaborationProposal
    extra = 0
    readonly_fields = [
        'proposed_by', 'proposed_by_agency',
        'client_agency_amount', 'property_agency_amount', 'total_amount',
        'created_at',
    ]
    can_delete = False


@admin.register(Collaboration)
class CollaborationAdmin(admin.ModelAdmin):
    list_display = [
        'property', 'client_agency', 'property_agency',
        'total_amount', 'status', 'created_at',
    ]
    list_filter  = ['status']
    search_fields = ['property__title', 'client_agency__name', 'property_agency__name']
    list_select_related = ['property', 'client_agency', 'property_agency']
    inlines = [CollaborationProposalInline]
