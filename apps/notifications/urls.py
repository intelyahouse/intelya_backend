from django.urls import path
from .views import MyNotificationsView, MarkReadView, MarkOneReadView

urlpatterns = [
    path('', MyNotificationsView.as_view(), name='my-notifications'),
    path('mark-read/', MarkReadView.as_view(), name='mark-read'),
    path('<uuid:notification_id>/mark-read/', MarkOneReadView.as_view(), name='mark-one-read'),
]