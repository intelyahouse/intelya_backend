from django.urls import path
from .views import (
    CreateLeaseView, SignLeaseView, MyLeasesView, LeaseContractPDFView,
    CreateAgentOwnerContractView, SignAgentOwnerContractView,
    MyAgentOwnerContractsView, AgentOwnerContractPDFView,
)

urlpatterns = [
    path('leases/', MyLeasesView.as_view(), name='my-leases'),
    path('leases/create/', CreateLeaseView.as_view(), name='create-lease'),
    path('leases/<uuid:lease_id>/sign/', SignLeaseView.as_view(), name='sign-lease'),
    path('leases/<uuid:lease_id>/pdf/', LeaseContractPDFView.as_view(), name='lease-pdf'),

    path('agent-owner/', MyAgentOwnerContractsView.as_view(), name='my-agent-owner-contracts'),
    path('agent-owner/create/', CreateAgentOwnerContractView.as_view(), name='create-agent-owner-contract'),
    path('agent-owner/<uuid:contract_id>/sign/', SignAgentOwnerContractView.as_view(), name='sign-agent-owner-contract'),
    path('agent-owner/<uuid:contract_id>/pdf/', AgentOwnerContractPDFView.as_view(), name='agent-owner-contract-pdf'),
]
