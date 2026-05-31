from django.urls import path
from .views import MyNotificationsView, MarkReadView

urlpatterns = [
    path('', MyNotificationsView.as_view(), name='my-notifications'),
    path('mark-read/', MarkReadView.as_view(), name='mark-read'),
]
