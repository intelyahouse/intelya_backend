from django.urls import path
from .views import PropertyReviewsView, AgentReviewsView, LeaveReviewView

urlpatterns = [
    path('property/<uuid:property_id>/', PropertyReviewsView.as_view(), name='property-reviews'),
    path('agent/<uuid:agent_id>/', AgentReviewsView.as_view(), name='agent-reviews'),
    path('leave/<uuid:visit_id>/', LeaveReviewView.as_view(), name='leave-review'),
]
