from django.urls import path
from .views import (
    PropertyListView, PropertyDetailView,
    CreatePropertyView, UpdatePropertyView,
    PropertyLikeView, MyFavoritesView,
    AgentPropertiesView, UploadPropertyPhotosView
)

urlpatterns = [
    path('', PropertyListView.as_view(), name='property-list'),
    path('create/', CreatePropertyView.as_view(), name='property-create'),
    path('favorites/', MyFavoritesView.as_view(), name='favorites'),
    path('agent/', AgentPropertiesView.as_view(), name='agent-properties'),
    path('<uuid:property_id>/', PropertyDetailView.as_view(), name='property-detail'),
    path('<uuid:property_id>/update/', UpdatePropertyView.as_view(), name='property-update'),
    path('<uuid:property_id>/like/', PropertyLikeView.as_view(), name='property-like'),
    path('<uuid:property_id>/photos/', UploadPropertyPhotosView.as_view(), name='property-photos'),
]
