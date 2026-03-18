from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework import viewsets
from ..models import VehicleType, Vehicle, VehicleDocument
from .serializers import VehicleTypeSerializer, VehicleSerializer, VehicleDocumentSerializer
from apps.drivers.models import DriverProfile
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.permissions import IsDriver
from django.contrib.auth import get_user_model


User = get_user_model()

class VehicleTypeViewSet(viewsets.ModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated, IsDriver]

    def get_driver(self):
        driver, _ = DriverProfile.objects.get_or_create(user=self.request.user)
        return driver

    def get_queryset(self):
        return Vehicle.objects.filter(driver=self.get_driver())

    def perform_create(self, serializer):
        serializer.save(driver=self.get_driver())

class VehicleDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleDocumentSerializer
    permission_classes = [IsAuthenticated, IsDriver]

    def get_queryset(self):

        return VehicleDocument.objects.filter(
            vehicle__driver__user=self.request.user
        )