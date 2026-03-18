from rest_framework import viewsets
from ..models import VehicleType, Vehicle, VehicleDocument
from .serializers import VehicleTypeSerializer, VehicleSerializer, VehicleDocumentSerializer
from apps.drivers.models import DriverProfile
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class VehicleTypeViewSet(viewsets.ModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        driver = DriverProfile.objects.get(user=self.request.user)

        return Vehicle.objects.filter(driver=driver)

    def perform_create(self, serializer):

        driver = DriverProfile.objects.get(user=self.request.user)

        serializer.save(driver=driver)

class VehicleDocumentViewSet(viewsets.ModelViewSet):

    serializer_class = VehicleDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        return VehicleDocument.objects.filter(
            vehicle__driver__user=self.request.user
        )