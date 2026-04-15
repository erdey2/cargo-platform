from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from ..models import Notification, Device, NotificationPreference
from .serializers import NotificationSerializer, DeviceSerializer, NotificationPreferenceSerializer

@extend_schema_view(
    list=extend_schema(
        summary="List notifications",
        parameters=[
            OpenApiParameter(
                name="unread",
                description="If true, only unread notifications are returned",
                required=False,
                type=str,
                enum=["true", "false"],
            )
        ],
    ),
    mark_read=extend_schema(summary="Mark one or all notifications as read"),
    unread_count=extend_schema(summary="Get unread notification count"),
)
class NotificationViewSet(ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).order_by("-created_at")
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(is_read=False)

        return qs

    @action(detail=False, methods=["post"])
    def mark_read(self, request):
        notification_id = request.data.get("id")
        user = request.user

        if notification_id:
            n = get_object_or_404(Notification, id=notification_id, recipient=user)
            n.is_read = True
            n.save()
        else:
            Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)

        return Response({"status": "ok"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread": count})


@extend_schema_view(
    summary="Get Device Info",
    create=extend_schema(summary="Register a device for FCM push notifications"),
    destroy=extend_schema(summary="Delete a registered device"),
)
class DeviceViewSet(ModelViewSet):
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        token = serializer.validated_data["fcm_token"]

        device, _ = Device.objects.update_or_create(
            fcm_token=token,
            defaults={
                "user": self.request.user,
                "platform": serializer.validated_data["platform"]
            }
        )
        serializer.instance = device

class NotificationPreferenceView(RetrieveUpdateAPIView):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj