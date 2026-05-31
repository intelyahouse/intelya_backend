from django.urls import path
from apps.users.views_admin import (
    AdminStatsView, AdminValidateUserView,
    AdminPendingUsersView, AdminBlockUserView,
    AdminAllUsersView, AdminDisputesView,
    AdminRevenueView, AdminAllPropertiesView,
    AdminAllTransactionsView, AdminAllReportsView,
    AdminPlatformConfigView, AdminAllBoostsView,
    AdminAllLeasesView
)

urlpatterns = [
    # Statistiques
    path('stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('revenue/', AdminRevenueView.as_view(), name='admin-revenue'),
    path('config/', AdminPlatformConfigView.as_view(), name='admin-config'),

    # Utilisateurs
    path('users/', AdminAllUsersView.as_view(), name='admin-users'),
    path('users/pending/', AdminPendingUsersView.as_view(), name='admin-pending'),
    path('users/<uuid:user_id>/validate/', AdminValidateUserView.as_view(), name='admin-validate'),
    path('users/<uuid:user_id>/block/', AdminBlockUserView.as_view(), name='admin-block'),

    # Biens
    path('properties/', AdminAllPropertiesView.as_view(), name='admin-properties'),
    path('properties/<uuid:property_id>/', AdminAllPropertiesView.as_view(), name='admin-property-update'),

    # Paiements
    path('transactions/', AdminAllTransactionsView.as_view(), name='admin-transactions'),

    # Litiges et signalements
    path('disputes/', AdminDisputesView.as_view(), name='admin-disputes'),
    path('disputes/<uuid:dispute_id>/decide/', AdminDisputesView.as_view(), name='admin-decide'),
    path('reports/', AdminAllReportsView.as_view(), name='admin-reports'),
    path('reports/<uuid:report_id>/action/', AdminAllReportsView.as_view(), name='admin-report-action'),

    # Boosts et baux
    path('boosts/', AdminAllBoostsView.as_view(), name='admin-boosts'),
    path('leases/', AdminAllLeasesView.as_view(), name='admin-leases'),
]
