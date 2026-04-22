from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.shipments.models import Shipment, ShipmentStatusHistory
from ..services.matching import MatchingService
from ..models import DriverOffer
from apps.assignment.models import Assignment
from core.permissions import IsAdminOrDriver
from .serializers import DriverPreviewSerializer, DriverOfferSerializer, DriverResponseSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@extend_schema(
    summary="Find nearest drivers for a shipment",
    description="Returns a list of nearby available drivers for a shipment that is in matching state.",
    parameters=[
        OpenApiParameter(
            name="shipment_id",
            description="ID of the shipment",
            required=True,
            type=int,
            location="path",
        ),
    ],
    responses={
        200: DriverPreviewSerializer(many=True),
        400: OpenApiResponse(description="Shipment not in matching state"),
        403: OpenApiResponse(description="Not allowed"),
        404: OpenApiResponse(description="Shipment not found"),
    },
)
class MatchDriversView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, shipment_id):
        try:
            shipment = Shipment.objects.get(id=shipment_id)
        except Shipment.DoesNotExist:
            raise NotFound("Shipment not found")

        if shipment.customer != request.user and not request.user.is_staff:
            raise PermissionDenied("Not allowed")

        if shipment.status != "matching":
            return Response({"error": "Shipment not in matching state"}, status=400)

        drivers = MatchingService.find_nearest_drivers(shipment)
        serializer = DriverPreviewSerializer(drivers, many=True)
        return Response(serializer.data)

@extend_schema(
    summary="Driver responds to an offer",
    description="""
Allows a driver to accept or reject a delivery offer.

### Possible actions:
- `accept` → Driver accepts the shipment
- `reject` → Driver rejects the offer and next driver is matched
""",
    request=DriverResponseSerializer,
    parameters=[
        OpenApiParameter(
            name="offer_id",
            description="ID of the driver offer",
            required=True,
            type=int,
            location="path",
        ),
    ],
    examples=[
        OpenApiExample(
            name="Accept Request",
            value={"action": "accept"},
            request_only=True,
        ),
        OpenApiExample(
            name="Reject Request",
            value={"action": "reject"},
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Success response",
            examples=[
                OpenApiExample(
                    name="Accepted",
                    value={"message": "Accepted"},
                ),
                OpenApiExample(
                    name="Rejected",
                    value={"message": "Rejected"},
                ),
            ],
        ),
        400: OpenApiResponse(description="Invalid action / already handled / expired"),
        403: OpenApiResponse(description="Not your offer"),
        404: OpenApiResponse(description="Offer not found"),
    },
)
class DriverResponseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, offer_id):

        serializer = DriverResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        try:
            with transaction.atomic():

                offer = (
                    DriverOffer.objects
                    .select_for_update(of=("self",))
                    .get(id=offer_id)
                )

                shipment = (
                    offer.shipment.__class__.objects
                    .select_for_update()
                    .get(id=offer.shipment_id)
                )

                # Ensure ownership
                if offer.driver.user != request.user:
                    raise PermissionDenied("Not your offer")

                # Already handled
                if offer.status != "pending":
                    return Response({"error": "Already handled"}, status=400)

                # Expired
                if offer.expires_at < timezone.now():
                    offer.status = "expired"
                    offer.save(update_fields=["status"])

                    MatchingService.match_next_driver(shipment)
                    return Response({"error": "Offer expired"}, status=400)

                # Prevent accepting already assigned shipment
                if shipment.status != "matching":
                    return Response({"error": "Already assigned"}, status=400)

                # ACCEPT FLOW
                if action == "accept":

                    vehicle = offer.vehicle
                    if not vehicle:
                        raise ValidationError("No vehicle assigned to this offer")

                    # Safe assignment creation
                    try:
                        Assignment.objects.create(
                            shipment=shipment,
                            driver=offer.driver,
                            vehicle=vehicle
                        )
                    except IntegrityError:
                        return Response({"error": "Already assigned"}, status=400)

                    # update offer
                    offer.status = "accepted"
                    offer.responded_at = timezone.now()
                    offer.save(update_fields=["status", "responded_at"])

                    # update driver
                    offer.driver.is_available = False
                    offer.driver.save(update_fields=["is_available"])

                    # update shipment
                    shipment.driver = offer.driver
                    shipment.status = "assigned"
                    shipment.assigned_at = timezone.now()
                    shipment.save(update_fields=["driver", "status", "assigned_at"])

                    # history
                    ShipmentStatusHistory.objects.create(
                        shipment=shipment,
                        status="assigned",
                        changed_by=request.user,
                        notes="Driver accepted offer"
                    )

                    # REAL-TIME notify customer
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"user_{shipment.customer.id}",
                        {
                            "type": "shipment_matched",
                            "data": {
                                "type": "matched",
                                "shipment_id": shipment.id,
                                "driver_id": offer.driver.id,
                            }
                        }
                    )

                    return Response({"message": "Accepted"})

                # REJECT FLOW
                elif action == "reject":

                    offer.status = "rejected"
                    offer.responded_at = timezone.now()
                    offer.save(update_fields=["status", "responded_at"])

                    # try next driver
                    MatchingService.match_next_driver(shipment)

                    # REAL-TIME update
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"user_{shipment.customer.id}",
                        {
                            "type": "shipment_update",
                            "data": {
                                "type": "driver_rejected",
                                "shipment_id": shipment.id,
                            }
                        }
                    )

                    return Response({"message": "Rejected"})

        except DriverOffer.DoesNotExist:
            raise NotFound("Offer not found")

@extend_schema(
    summary="List driver offers",
    description=(
        "Retrieve driver offers.\n\n"
        "- Drivers → see ONLY their offers\n"
        "- Admins → see ALL offers\n\n"
        "Optional filter:\n"
        "- status: pending, accepted, rejected, expired"
    ),
    parameters=[
        OpenApiParameter(
            name="status",
            description="Filter by offer status",
            required=False,
            type=str,
        ),
    ],
    responses={
        200: DriverOfferSerializer(many=True),
        403: OpenApiResponse(description="Only drivers and admins can view offers"),
    },
)
class DriverOfferViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DriverOfferSerializer
    permission_classes = [IsAuthenticated, IsAdminOrDriver]

    def get_queryset(self):
        user = self.request.user
        status_param = self.request.query_params.get("status")

        base_qs = DriverOffer.objects.select_related(
            "shipment",
            "driver__user"
        )

        if user.is_staff or user.is_superuser:
            queryset = base_qs

        elif getattr(user, "role", None) == "driver":
            queryset = base_qs.filter(driver__user=user)

        else:
            return DriverOffer.objects.none()

        # VALIDATE STATUS FILTER
        if status_param:
            valid_statuses = [choice[0] for choice in DriverOffer.STATUS_CHOICES]

            if status_param not in valid_statuses:
                return DriverOffer.objects.none()

            queryset = queryset.filter(status=status_param)

        return queryset.order_by("-created_at")