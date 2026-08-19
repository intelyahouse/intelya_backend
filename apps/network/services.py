from django.db import transaction
from django.utils import timezone

from .models import Collaboration, CollaborationProposal


@transaction.atomic
def create_collaboration(initiator, property_obj, client_agency, property_agency,
                          client_agency_amount, property_agency_amount, client=None):
    total = client_agency_amount + property_agency_amount
    collaboration = Collaboration.objects.create(
        property=property_obj, client=client,
        client_agency=client_agency, property_agency=property_agency,
        initiated_by=initiator,
        client_agency_amount=client_agency_amount,
        property_agency_amount=property_agency_amount,
        total_amount=total,
        status="proposed",
        last_proposed_by_agency=client_agency,
    )
    CollaborationProposal.objects.create(
        collaboration=collaboration, proposed_by=initiator, proposed_by_agency=client_agency,
        client_agency_amount=client_agency_amount,
        property_agency_amount=property_agency_amount,
        total_amount=total,
    )
    return collaboration


@transaction.atomic
def counter_propose(collaboration, proposer, proposer_agency, client_agency_amount, property_agency_amount):
    total = client_agency_amount + property_agency_amount
    collaboration.client_agency_amount = client_agency_amount
    collaboration.property_agency_amount = property_agency_amount
    collaboration.total_amount = total
    collaboration.status = "proposed"
    collaboration.last_proposed_by_agency = proposer_agency
    collaboration.responded_by = None
    collaboration.responded_at = None
    collaboration.save(update_fields=[
        "client_agency_amount", "property_agency_amount", "total_amount",
        "status", "last_proposed_by_agency", "responded_by", "responded_at", "updated_at",
    ])
    CollaborationProposal.objects.create(
        collaboration=collaboration, proposed_by=proposer, proposed_by_agency=proposer_agency,
        client_agency_amount=client_agency_amount,
        property_agency_amount=property_agency_amount,
        total_amount=total,
    )
    return collaboration


def respond_collaboration(collaboration, responder, accept):
    collaboration.status = "accepted" if accept else "rejected"
    collaboration.responded_by = responder
    collaboration.responded_at = timezone.now()
    collaboration.save(update_fields=["status", "responded_by", "responded_at", "updated_at"])
    return collaboration
