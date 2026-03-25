from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.shipments.models import Shipment
from ..services.matching import MatchingService
from ..models import DriverOffer
from apps.assignment.models import Assignment
from .serializers import DriverPreviewSerializer, DriverOfferSerializer, DriverResponseSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample


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
    description="Allows a driver to accept or reject a delivery offer.",
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
    responses={
        200: OpenApiResponse(
            description="Response message",
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
                offer = DriverOffer.objects.select_for_update().get(id=offer_id)

                if offer.driver.user != request.user:
                    raise PermissionDenied("Not your offer")

                if offer.status != "pending":
                    return Response({"error": "Already handled"}, status=400)

                if offer.expires_at < timezone.now():
                    offer.status = "expired"
                    offer.save()
                    MatchingService.match_next_driver(offer.shipment)
                    return Response({"error": "Offer expired"}, status=400)

                if action == "accept":
                    offer.status = "accepted"
                    offer.responded_at = timezone.now()
                    offer.save()

                    if hasattr(offer.shipment, "assignment"):
                        return Response({"error": "Already assigned"}, status=400)

                    vehicle = offer.driver.vehicles.filter(
                        capacity_weight__gte=offer.shipment.weight,
                        capacity_volume__gte=offer.shipment.volume
                    ).first()

                    Assignment.objects.create(
                        shipment=offer.shipment,
                        driver=offer.driver,
                        vehicle=vehicle
                    )

                    offer.driver.is_available = False
                    offer.driver.save(update_fields=["is_available"])

                    shipment = offer.shipment
                    shipment.status = "assigned"
                    shipment.save(update_fields=["status"])

                    return Response({"message": "Accepted"})

                elif action == "reject":
                    offer.status = "rejected"
                    offer.responded_at = timezone.now()
                    offer.save()

                    MatchingService.match_next_driver(offer.shipment)
                    return Response({"message": "Rejected"})

        except DriverOffer.DoesNotExist:
            raise NotFound("Offer not found")

@extend_schema(
    summary="List driver offers",
    description="Retrieve driver offers. Drivers see their own offers, admins see all offers.",
    parameters=[
        OpenApiParameter(
            name="status",
            description="Filter offers by status (pending, accepted, rejected, expired)",
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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        status_param = self.request.query_params.get("status")

        # Admins can see all offers
        if user.is_staff or user.is_superuser:
            queryset = DriverOffer.objects.all()

        # Drivers see only their own offers
        elif hasattr(user, "driver_profile"):
            queryset = DriverOffer.objects.filter(driver__user=user)
            
        # Other roles (e.g., customers) are denied
        else:
            raise PermissionDenied("Only drivers and admins can view offers")

        # Apply optional status filter
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset.order_by("-created_at")