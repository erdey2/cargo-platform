from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.shipments.models import Shipment
from apps.matching.services.matching import MatchingService


class MatchDriversView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, shipment_id):

        shipment = Shipment.objects.get(id=shipment_id)

        drivers = MatchingService.find_nearest_drivers(shipment)

        data = []

        for d in drivers:
            data.append({
                "driver": d.driver.user.email,
                "distance": d.distance.m
            })

        return Response(data)