from django.urls import path
from .views import (
    AIMatchView,
    PropertyListView, PropertyDetailView,
    CreatePropertyView, UpdatePropertyView,
    PropertyLikeView, MyFavoritesView,
    AgentPropertiesView, UploadPropertyPhotosView,
    PropertyVideoAccessView
)
from .views import FeaturedPropertiesView

urlpatterns = [
    path('', PropertyListView.as_view(), name='property-list'),
    path('featured/', FeaturedPropertiesView.as_view(), name='property-featured'),
    path('create/', CreatePropertyView.as_view(), name='property-create'),
    path('favorites/', MyFavoritesView.as_view(), name='favorites'),
    path('agent/', AgentPropertiesView.as_view(), name='agent-properties'),
    path('<uuid:property_id>/', PropertyDetailView.as_view(), name='property-detail'),
    path('<uuid:property_id>/update/', UpdatePropertyView.as_view(), name='property-update'),
    path('<uuid:property_id>/like/', PropertyLikeView.as_view(), name='property-like'),
    path('<uuid:property_id>/photos/', UploadPropertyPhotosView.as_view(), name='property-photos'),
    path('<uuid:property_id>/video/', PropertyVideoAccessView.as_view(), name='property-video'),
    path('ai-match/', AIMatchView.as_view(), name='ai-match'),
]
