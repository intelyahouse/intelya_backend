from django.contrib import admin
from .models import Dispute, Report


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display  = ['title', 'claimant', 'defendant', 'agency', 'dispute_type', 'status', 'decision', 'created_at']
    list_filter   = ['status', 'dispute_type', 'decision']
    search_fields = ['title', 'claimant__email', 'defendant__email', 'agency__name']

    actions = ['mark_reviewing']

    def mark_reviewing(self, request, queryset):
        queryset.update(status='reviewing')
        self.message_user(request, f"{queryset.count()} litige(s) en examen")
    mark_reviewing.short_description = "🔍 Marquer en examen"


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display  = ['reporter', 'reported', 'reason', 'status', 'created_at']
    list_filter   = ['reason', 'status']
    search_fields = ['reporter__email', 'reported__email']
