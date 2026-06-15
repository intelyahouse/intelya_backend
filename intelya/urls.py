
# INTELYA HAVEN - URLs principales


from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.health import HealthCheckView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


# API v1 URLs
api_v1_patterns = [
    # Auth
    path('auth/', include('apps.users.urls.auth')),

    # Utilisateurs
    path('users/', include('apps.users.urls.users')),

    # Agents
    path('agents/', include('apps.agents.urls')),

    # Propriétaires
    path('owners/', include('apps.owners.urls')),

    # Biens immobiliers
    path('properties/', include('apps.properties.urls')),

    # Visites
    path('visits/', include('apps.visits.urls')),

    # Contrats
    path('contracts/', include('apps.contracts.urls')),

    # Gestion locative
    path('leases/', include('apps.leases.urls')),

    # Paiements
    path('payments/', include('apps.payments.urls')),

    # Messagerie et Forum
    path('messaging/', include('apps.messaging.urls')),

    # Notifications
    path('notifications/', include('apps.notifications.urls')),

    # Avis et notations
    path('reviews/', include('apps.reviews.urls')),

    # Litiges et Signalements
    path('disputes/', include('apps.disputes.urls')),

    # Boost agents
    path('boost/', include('apps.boost.urls')),

    # Parrainage
    path('referrals/', include('apps.referrals.urls')),
    # Admin Panel API
    path('admin-panel/', include('apps.users.urls.admin_urls')),
]

urlpatterns = [
    # Admin Django
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/', include(api_v1_patterns)),

    # Swagger Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # OAuth
    path('accounts/', include('allauth.urls')),
    path('api/health/', HealthCheckView.as_view(), name='health'),
    path('api/v1/health/', HealthCheckView.as_view(), name='health-v1'),
]

# Fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



# ===================================
# Handlers d'erreurs globaux
# ===================================
handler400 = 'core.error_handlers.bad_request'
handler403 = 'core.error_handlers.permission_denied'
handler404 = 'core.error_handlers.page_not_found'
handler500 = 'core.error_handlers.server_error'
