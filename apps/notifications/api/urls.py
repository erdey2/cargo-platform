from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, DeviceViewSet, NotificationPreferenceView

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notifications')
router.register(r'devices', DeviceViewSet, basename='devices')

urlpatterns = [
    path('', include(router.urls)),
    path("notification-preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
]