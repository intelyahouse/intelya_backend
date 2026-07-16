from django.urls import path
from .views import (
    RequestVisitView, ScheduleVisitView,
    ConfirmGPSView, AgentConfirmVisitView,
    CancelVisitView, MyVisitsView, LeaveReviewView
)

urlpatterns = [
    path('', MyVisitsView.as_view(), name='my-visits'),
    path('request/', RequestVisitView.as_view(), name='request-visit'),
    path('<uuid:visit_id>/schedule/', ScheduleVisitView.as_view(), name='schedule-visit'),
    path('<uuid:visit_id>/confirm-gps/', ConfirmGPSView.as_view(), name='confirm-gps'),
    path('<uuid:visit_id>/agent-confirm/', AgentConfirmVisitView.as_view(), name='agent-confirm'),
    path('<uuid:visit_id>/cancel/', CancelVisitView.as_view(), name='cancel-visit'),
    path('<uuid:visit_id>/review/', LeaveReviewView.as_view(), name='leave-review'),
]
