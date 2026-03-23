from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from ..models import Shipment, CargoType, ShipmentStatusHistory
from .serializers import ShipmentSerializer, CargoTypeSerializer, ShipmentStatusHistorySerializer
from apps.matching.services.matching import MatchingService
from apps.pricing.services.pricing_service import PriceCalculator
from core.permissions import IsAdminOrReadOnly
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample


@extend_schema(
    tags=["Shipments"]
)
@extend_schema_view(
    create=extend_schema(
        summary="Create shipment",
        description="Create a shipment and trigger pricing + driver matching.",
        examples=[
            OpenApiExample(
                "Shipment Example",
                value={
                    "pickup_address": "Bole",
                    "dropoff_address": "Piassa",
                    "pickup_lat": 9.03,
                    "pickup_lng": 38.74,
                    "dropoff_lat": 9.05,
                    "dropoff_lng": 38.76,
                    "weight": 50,
                    "volume": 2.5,
                    "cargo_type": 1,
                    "description": "Electronics"
                },
                request_only=True
            )
        ],
        responses={201: ShipmentSerializer}
    )
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
        shipment = serializer.save(
            customer=self.request.user,
            status="matching"
        )

        try:
            shipment.estimated_price = PriceCalculator.calculate_estimated_price(shipment)
            shipment.save()
        except Exception:
            raise ValidationError("Failed to calculate price")

        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status=shipment.status,
            changed_by=self.request.user
        )

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

        if not shipment_id:
            raise ValidationError("shipment_id is required")

        return ShipmentStatusHistory.objects.filter(
            shipment_id=shipment_id
        )