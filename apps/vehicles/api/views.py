from rest_framework import viewsets, status
from ..models import VehicleType, Vehicle, VehicleDocument
from .serializers import VehicleTypeSerializer, VehicleSerializer, VehicleDocumentSerializer
from apps.drivers.models import DriverProfile
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.permissions import IsDriver
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view

User = get_user_model()

@extend_schema(
    tags=["Vehicle Types"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List all vehicle types",
        description="Retrieve all vehicle types (Admin only).",
        responses={200: VehicleTypeSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Create vehicle type",
        description="Create a new vehicle type (Admin only).",
        request=VehicleTypeSerializer,
        responses={201: VehicleTypeSerializer}
    ),
    retrieve=extend_schema(
        summary="Retrieve vehicle type",
        description="Get a specific vehicle type by ID.",
        responses={200: VehicleTypeSerializer}
    ),
    update=extend_schema(
        summary="Update vehicle type",
        description="Update an existing vehicle type.",
        request=VehicleTypeSerializer,
        responses={200: VehicleTypeSerializer}
    ),
    partial_update=extend_schema(
        summary="Partially update vehicle type",
        request=VehicleTypeSerializer,
        responses={200: VehicleTypeSerializer}
    ),
    destroy=extend_schema(
        summary="Delete vehicle type",
        responses={204: None}
    ),
)
class VehicleTypeViewSet(viewsets.ModelViewSet):
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

@extend_schema(
    tags=["Vehicles"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List driver's vehicles",
        description="Retrieve all vehicles belonging to the authenticated driver.",
        responses={200: VehicleSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Register a vehicle",
        description="Driver registers a new vehicle.",
        request=VehicleSerializer,
        responses={201: VehicleSerializer}
    ),
    retrieve=extend_schema(
        summary="Retrieve vehicle",
        description="Get details of a specific vehicle owned by the driver.",
        responses={200: VehicleSerializer}
    ),
    update=extend_schema(
        summary="Update vehicle",
        description="Update a vehicle owned by the driver.",
        request=VehicleSerializer,
        responses={200: VehicleSerializer}
    ),
    partial_update=extend_schema(
        summary="Partially update vehicle",
        request=VehicleSerializer,
        responses={200: VehicleSerializer}
    ),
    destroy=extend_schema(
        summary="Delete vehicle",
        responses={204: None}
    ),
)
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

@extend_schema(
    tags=["Vehicle Documents"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List vehicle documents",
        description="Retrieve all documents for vehicles owned by the authenticated driver.",
        responses={200: VehicleDocumentSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Upload vehicle document",
        description="Upload a document for a vehicle.",
        request=VehicleDocumentSerializer,
        responses={201: VehicleDocumentSerializer}
    ),
    retrieve=extend_schema(
        summary="Retrieve vehicle document",
        description="Get a specific vehicle document.",
        responses={200: VehicleDocumentSerializer}
    ),
    update=extend_schema(
        summary="Update vehicle document",
        description="Update an existing vehicle document.",
        request=VehicleDocumentSerializer,
        responses={200: VehicleDocumentSerializer}
    ),
    partial_update=extend_schema(
        summary="Partially update vehicle document",
        request=VehicleDocumentSerializer,
        responses={200: VehicleDocumentSerializer}
    ),
    destroy=extend_schema(
        summary="Delete vehicle document",
        responses={204: None}
    ),
)
class VehicleDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleDocumentSerializer
    permission_classes = [IsAuthenticated, IsDriver]

    def get_queryset(self):
        return VehicleDocument.objects.filter(
            vehicle__driver__user=self.request.user
        )