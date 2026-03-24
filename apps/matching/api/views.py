from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.shipments.models import Shipment
from ..services.matching import MatchingService
from ..models import DriverOffer
from apps.assignment.models import Assignment


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
            return Response(
                {"error": "Shipment not in matching state"},
                status=400
            )

        drivers = MatchingService.find_nearest_drivers(shipment)

        data = [
            {
                "driver": d.driver.user.email,
                "distance_km": round(d.distance.m / 1000, 2)
            }
            for d in drivers
        ]

        return Response(data)

class DriverResponseView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, offer_id):

        try:
            offer = DriverOffer.objects.get(id=offer_id)
        except DriverOffer.DoesNotExist:
            raise NotFound("Offer not found")

        if offer.driver.user != request.user:
            raise PermissionDenied("Not your offer")

        if offer.status != "pending":
            return Response({"error": "Already handled"}, status=400)

        if offer.expires_at < timezone.now():
            offer.status = "expired"
            offer.save()
            return Response({"error": "Offer expired"}, status=400)

        action = request.data.get("action")

        if action == "accept":

            offer.status = "accepted"
            offer.responded_at = timezone.now()
            offer.save()

            # create FINAL assignment
            Assignment.objects.create(
                shipment=offer.shipment,
                driver=offer.driver,
                vehicle=offer.driver.vehicles.first()  # improve later
            )

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

        return Response({"error": "Invalid action"}, status=400)