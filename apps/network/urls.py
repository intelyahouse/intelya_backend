from django.urls import path
from .views import (
    AgencySearchView, CollaborationListCreateView,
    CollaborationRespondView, CollaborationCounterProposeView,
    CollaborationCancelView,
)

urlpatterns = [
    path('agencies/', AgencySearchView.as_view(), name='network-agency-search'),
    path('collaborations/', CollaborationListCreateView.as_view(), name='network-collaborations'),
    path('collaborations/<uuid:collaboration_id>/respond/', CollaborationRespondView.as_view(), name='network-collaboration-respond'),
    path('collaborations/<uuid:collaboration_id>/counter-propose/', CollaborationCounterProposeView.as_view(), name='network-collaboration-counter'),
    path('collaborations/<uuid:collaboration_id>/cancel/', CollaborationCancelView.as_view(), name='network-collaboration-cancel'),
]
