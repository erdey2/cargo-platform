from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.shipments.models import Shipment
from apps.shipments.api.serializers import ShipmentSerializer
from apps.assignment.models import Assignment


@extend_schema(tags=["Driver - Shipments"])
class DriverShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Shipment.objects.filter(
            assignment__driver__user=self.request.user
        ).order_by("-created_at")

    @extend_schema(
        summary="List all driver shipments",
        description="Returns all shipments assigned to the authenticated driver.",
        responses={
            200: ShipmentSerializer(many=True),
        },
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve shipment details",
        description="Get details of a specific shipment assigned to the driver.",
        responses={
            200: ShipmentSerializer,
            404: OpenApiResponse(description="Shipment not found"),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, url_path="active")
    @extend_schema(
        summary="Get active shipments",
        description="""
Returns shipments that are currently active:
- **assigned**
- **in_transit**
""",
        responses={
            200: ShipmentSerializer(many=True),
        },
    )
    def active(self, request):
        qs = self.get_queryset().filter(
            status__in=["assigned", "in_transit"]
        )
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, url_path="completed")
    @extend_schema(
        summary="Get completed shipments",
        description="Returns all delivered shipments for the driver.",
        responses={
            200: ShipmentSerializer(many=True),
        },
    )
    def completed(self, request):
        qs = self.get_queryset().filter(
            status="completed"
        )
        return Response(self.get_serializer(qs, many=True).data)