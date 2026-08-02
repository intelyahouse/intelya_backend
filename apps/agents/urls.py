from django.urls import path
from .views import (
    AgentListView, AgentProfileView, AgentPublicProfileView,
    AgentClientsView, AgentClientHistoryView, AgentOwnersView,
    AgentAvailabilityView, ChooseAgentView, AgentReportsView
)

urlpatterns = [
    path('', AgentListView.as_view(), name='agent-list'),
    path('me/', AgentProfileView.as_view(), name='agent-profile'),
    path('choose/', ChooseAgentView.as_view(), name='choose-agent'),
    path('me/clients/', AgentClientsView.as_view(), name='agent-clients'),
    path('me/clients/<uuid:client_id>/history/', AgentClientHistoryView.as_view(), name='agent-client-history'),
    path('me/owners/', AgentOwnersView.as_view(), name='agent-owners'),
    path('me/reports/', AgentReportsView.as_view(), name='agent-reports'),
    path('me/availability/', AgentAvailabilityView.as_view(), name='agent-availability'),
    path('me/availability/<uuid:slot_id>/', AgentAvailabilityView.as_view(), name='agent-availability-detail'),
    path('<uuid:agent_id>/', AgentPublicProfileView.as_view(), name='agent-public-profile'),
]