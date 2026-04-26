from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Shipment, CargoType, ShipmentStatusHistory
from .serializers import ShipmentSerializer, CargoTypeSerializer, ShipmentStatusHistorySerializer
from apps.pricing.services.pricing_service import PriceCalculator
from core.permissions import IsAdminOrReadOnly
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from apps.matching.tasks import start_driver_matching

@extend_schema(
    tags=["Shipments"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List shipments",
        description=(
            "Retrieve shipments.\n\n"
            "- Admins: see all shipments\n"
            "- Customers: see only their own shipments"
        ),
        responses={200: ShipmentSerializer(many=True)},
    ),

    create=extend_schema(
        summary="Create shipment",
        description=(
            "Create a new shipment.\n\n"
            "System automatically:\n"
            "- Assigns current user as customer\n"
            "- Sets status to `matching`\n"
            "- Calculates estimated price\n"
            "- Creates status history\n"
            "- Triggers driver matching"
        ),
        examples=[
            OpenApiExample(
                "Shipment Request Example",
                value={
                    "pickup_address": "Bole, Addis Ababa",
                    "dropoff_address": "Piassa, Addis Ababa",
                    "pickup_lat": 9.03,
                    "pickup_lng": 38.74,
                    "dropoff_lat": 9.05,
                    "dropoff_lng": 38.76,
                    "weight": 50,
                    "volume": 2.5,
                    "cargo_type": 1,
                    "description": "Electronics",
                    "recipient_name": "Abel Tesfaye",
                    "recipient_phone": "+251912345678",
                    "recipient_alternate_phone": "+251987654321"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Shipment Response Example",
                value={
                    "id": 1,
                    "customer": 5,
                    "pickup_address": "Bole, Addis Ababa",
                    "dropoff_address": "Piassa, Addis Ababa",
                    "pickup_latitude": 9.03,
                    "pickup_longitude": 38.74,
                    "dropoff_latitude": 9.05,
                    "dropoff_longitude": 38.76,
                    "weight": 50,
                    "volume": 2.5,
                    "cargo_type": 1,
                    "description": "Electronics",
                    "status": "matching",
                    "estimated_price": "1500.00",
                    "final_price": None,
                    "assigned_at": None,
                    "picked_up_at": None,
                    "delivered_at": None,
                    "created_at": "2026-03-23T10:00:00Z"
                },
                response_only=True,
            ),
        ],
        responses={201: ShipmentSerializer},
    ),

    retrieve=extend_schema(
        summary="Retrieve shipment",
        description="Get detailed information about a specific shipment.",
        responses={200: ShipmentSerializer},
    ),

    update=extend_schema(
        summary="Update shipment",
        description="Update shipment details (only allowed before assignment).",
        request=ShipmentSerializer,
        responses={200: ShipmentSerializer},
    ),

    partial_update=extend_schema(
        summary="Partially update shipment",
        description="Update specific fields of a shipment.",
        request=ShipmentSerializer,
        responses={200: ShipmentSerializer},
    ),

    destroy=extend_schema(
        summary="Delete shipment",
        description=(
            "Cancel a shipment by setting status to `cancelled`.\n\n"
            "- Customers: only allowed when status is `created` or `matching`\n"
            "- Admins: allowed to cancel from this endpoint"
        ),
        responses={204: None},
    ),
)
class ShipmentViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    CUSTOMER_CANCELLABLE_STATUSES = {"created", "matching"}

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
        start_driver_matching.delay(shipment.id)

        # MatchingService.match_driver(shipment)

    def destroy(self, request, *args, **kwargs):
        shipment = self.get_object()

        if shipment.status == "cancelled":
            return Response(
                {"detail": "Shipment already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.is_staff and shipment.status not in self.CUSTOMER_CANCELLABLE_STATUSES:
            return Response(
                {"detail": "Customers can cancel only when shipment is in created or matching status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cancelled_by = "admin" if request.user.is_staff else "customer"
        shipment.status = "cancelled"
        shipment.save(update_fields=["status", "updated_at"])

        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status="cancelled",
            changed_by=request.user,
            notes=f"Cancelled by {cancelled_by}",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


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
        shipment_id = self.request.query_params.get("shipment_id")
        if not shipment_id:
            raise ValidationError("shipment_id query param is required")

        queryset = ShipmentStatusHistory.objects.filter(shipment_id=shipment_id)
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(shipment__customer=user)