from django.contrib import admin
from .models import Property, PropertyPhoto, PropertyVideo, FloorPlan, PropertyLike


class PropertyPhotoInline(admin.TabularInline):
    model = PropertyPhoto
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display  = ['title', 'property_type', 'status', 'city', 'neighborhood', 'price', 'is_verified', 'owner', 'agent']
    list_filter   = ['status', 'property_type', 'city', 'is_verified', 'is_furnished']
    search_fields = ['title', 'city', 'neighborhood', 'full_address']
    inlines       = [PropertyPhotoInline]
    readonly_fields = ['views_count', 'likes_count', 'interested_count']

    actions = ['verify_properties', 'suspend_properties']

    def verify_properties(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f"{queryset.count()} bien(s) vérifié(s)")
    verify_properties.short_description = "✅ Vérifier les biens sélectionnés"

    def suspend_properties(self, request, queryset):
        queryset.update(status='suspended')
        self.message_user(request, f"{queryset.count()} bien(s) suspendu(s)")
    suspend_properties.short_description = "🚫 Suspendre les biens"


@admin.register(PropertyPhoto)
class PropertyPhotoAdmin(admin.ModelAdmin):
    list_display = ['property', 'is_cover', 'order']


@admin.register(PropertyLike)
class PropertyLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'property', 'created_at']
