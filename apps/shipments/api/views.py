from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import Shipment, CargoType, ShipmentStatusHistory
from .serializers import ShipmentSerializer, CargoTypeSerializer, ShipmentStatusHistorySerializer
from apps.matching.services.matching import MatchingService
from apps.pricing.services.pricing_service import PriceCalculator
from core.permissions import IsAdminOrReadOnly
from drf_spectacular.utils import extend_schema, extend_schema_view

@extend_schema(
    tags=["Shipments"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List shipments",
        description="Retrieve all shipments. Admins see all shipments, customers see only their own.",
        responses={200: ShipmentSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Create shipment",
        description=(
            "Create a new shipment.\n\n"
            "System will automatically:\n"
            "- Assign the current user as customer\n"
            "- Calculate estimated price\n"
            "- Create shipment status history (created)\n"
            "- Trigger driver matching process"
        ),
        request=ShipmentSerializer,
        responses={201: ShipmentSerializer}
    ),
    retrieve=extend_schema(
        summary="Retrieve shipment",
        description="Get details of a specific shipment.",
        responses={200: ShipmentSerializer}
    ),
    update=extend_schema(
        summary="Update shipment",
        description="Update shipment details.",
        request=ShipmentSerializer,
        responses={200: ShipmentSerializer}
    ),
    partial_update=extend_schema(
        summary="Partially update shipment",
        request=ShipmentSerializer,
        responses={200: ShipmentSerializer}
    ),
    destroy=extend_schema(
        summary="Delete shipment",
        description="Delete a shipment.",
        responses={204: None}
    ),
)
class ShipmentViewSet(viewsets.ModelViewSet):

    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Shipment.objects.all()

        return Shipment.objects.filter(customer=user)

    def perform_create(self, serializer):

        # Create shipment
        shipment = serializer.save(
            customer=self.request.user
        )

        # Calculate estimated price
        shipment.estimated_price = PriceCalculator.calculate_estimated_price(shipment)
        shipment.save()

        # Save status history
        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status="created",
            changed_by=self.request.user
        )

        # Start driver matching
        MatchingService.match_driver(shipment)

@extend_schema(
    tags=["Cargo Types"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List cargo types",
        description="Retrieve all cargo types.",
        responses={200: CargoTypeSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Create cargo type",
        description="Create a new cargo type (Admin only).",
        request=CargoTypeSerializer,
        responses={201: CargoTypeSerializer}
    ),
    retrieve=extend_schema(
        summary="Retrieve cargo type",
        responses={200: CargoTypeSerializer}
    ),
    update=extend_schema(
        summary="Update cargo type",
        request=CargoTypeSerializer,
        responses={200: CargoTypeSerializer}
    ),
    partial_update=extend_schema(
        summary="Partially update cargo type",
        request=CargoTypeSerializer,
        responses={200: CargoTypeSerializer}
    ),
    destroy=extend_schema(
        summary="Delete cargo type",
        responses={204: None}
    ),
)
class CargoTypeViewSet(viewsets.ModelViewSet):
    queryset = CargoType.objects.all()
    serializer_class = CargoTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

@extend_schema(
    tags=["Shipment History"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List shipment status history",
        description="Retrieve status history for a specific shipment using shipment_id.",
        responses={200: ShipmentStatusHistorySerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Retrieve status record",
        description="Get a specific status history record.",
        responses={200: ShipmentStatusHistorySerializer}
    ),
)
class ShipmentStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = ShipmentStatusHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shipment_id = self.kwargs.get("shipment_id")

        return ShipmentStatusHistory.objects.filter(
            shipment_id=shipment_id
        )