from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import Shipment, CargoType, ShipmentStatusHistory
from .serializers import ShipmentSerializer, CargoTypeSerializer, ShipmentStatusHistorySerializer
from apps.matching.services.matching import MatchingService
from apps.pricing.services.pricing_service import PriceCalculator


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


class CargoTypeViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CargoType.objects.all()
    serializer_class = CargoTypeSerializer
    permission_classes = [IsAuthenticated]

class ShipmentStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = ShipmentStatusHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        shipment_id = self.kwargs.get("shipment_id")

        return ShipmentStatusHistory.objects.filter(
            shipment_id=shipment_id
        )