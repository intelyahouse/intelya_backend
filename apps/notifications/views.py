from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import Notification
from .serializers import NotificationSerializer
from core.utils import success_response


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Notifications'], summary="Mes notifications")
    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        unread_count  = notifications.filter(is_read=False).count()
        serializer    = NotificationSerializer(notifications[:50], many=True)
        return Response(success_response({
            'unread_count': unread_count,
            'notifications': serializer.data
        }))


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Notifications'], summary="Marquer toutes les notifications comme lues")
    def post(self, request):
        Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response(success_response(message="Toutes les notifications marquées comme lues ✅"))

class MarkOneReadView(APIView):
    """Marquer une seule notification comme lue"""
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        try:
            notif = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=['is_read', 'read_at'])
            return Response({'success': True, 'message': 'Notification marquée comme lue'})
        except Notification.DoesNotExist:
            return Response(
                {'success': False, 'message': 'Notification introuvable'},
                status=404
            )
