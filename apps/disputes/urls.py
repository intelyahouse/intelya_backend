from django.urls import path
from .views import CreateDisputeView, RespondDisputeView, MyDisputesView, CreateReportView

urlpatterns = [
    path('disputes/', MyDisputesView.as_view(), name='my-disputes'),
    path('disputes/create/', CreateDisputeView.as_view(), name='create-dispute'),
    path('disputes/<uuid:dispute_id>/respond/', RespondDisputeView.as_view(), name='respond-dispute'),
    path('reports/create/', CreateReportView.as_view(), name='create-report'),
]
