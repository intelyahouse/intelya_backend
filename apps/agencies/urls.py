from django.urls import path
from .views import (
    AgencyMeView, AgencyInviteView, AgencyInvitationCancelView,
    MyAgencyInvitationsView, RespondAgencyInvitationView,
    AgencyMemberRemoveView, AgencyLeaveView, MandateReassignView,
)

urlpatterns = [
    path('me/', AgencyMeView.as_view(), name='agency-me'),
    path('me/invite/', AgencyInviteView.as_view(), name='agency-invite'),
    path('me/invitations/<uuid:invitation_id>/', AgencyInvitationCancelView.as_view(), name='agency-invitation-cancel'),
    path('me/members/<uuid:user_id>/remove/', AgencyMemberRemoveView.as_view(), name='agency-member-remove'),
    path('me/leave/', AgencyLeaveView.as_view(), name='agency-leave'),
    path('invitations/received/', MyAgencyInvitationsView.as_view(), name='agency-invitations-received'),
    path('invitations/<uuid:invitation_id>/respond/', RespondAgencyInvitationView.as_view(), name='agency-invitation-respond'),
    path('mandates/<uuid:relation_id>/reassign/', MandateReassignView.as_view(), name='mandate-reassign'),
]
