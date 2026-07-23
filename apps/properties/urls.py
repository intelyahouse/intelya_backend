from django.urls import path
from .views import (
    AIMatchView,
    PropertiesByAgentView,
    PropertyListView, PropertyDetailView,
    CreatePropertyView, UpdatePropertyView,
    PropertyLikeView, MyFavoritesView,
    AgentPropertiesView, UploadPropertyPhotosView
)
from .views import FeaturedPropertiesView

urlpatterns = [
    path('', PropertyListView.as_view(), name='property-list'),
    path('featured/', FeaturedPropertiesView.as_view(), name='property-featured'),
    path('by-agent/', PropertiesByAgentView.as_view(), name='properties-by-agent'),  # AJOUTÉ
    path('create/', CreatePropertyView.as_view(), name='property-create'),
    path('favorites/', MyFavoritesView.as_view(), name='favorites'),
    path('agent/', AgentPropertiesView.as_view(), name='agent-properties'),
    path('<uuid:property_id>/', PropertyDetailView.as_view(), name='property-detail'),
    path('<uuid:property_id>/update/', UpdatePropertyView.as_view(), name='property-update'),
    path('<uuid:property_id>/like/', PropertyLikeView.as_view(), name='property-like'),
    path('<uuid:property_id>/photos/', UploadPropertyPhotosView.as_view(), name='property-photos'),
    path('ai-match/', AIMatchView.as_view(), name='ai-match'),
]
