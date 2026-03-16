from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.gis.geos import Point
from ..models import DriverLocation
from .serializers import DriverLocationSerializer
from apps.drivers.models import DriverProfile
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D


class UpdateDriverLocationView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        driver = DriverProfile.objects.get(user=request.user)

        lat = request.data.get("lat")
        lng = request.data.get("lng")

        location = Point(float(lng), float(lat))

        driver_location, created = DriverLocation.objects.update_or_create(
            driver=driver,
            defaults={
                "location": location,
                "heading": request.data.get("heading"),
                "speed": request.data.get("speed"),
                "is_online": True
            }
        )

        serializer = DriverLocationSerializer(driver_location)

        return Response(serializer.data)

class DriverLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, driver_id):

        location = DriverLocation.objects.get(driver_id=driver_id)

        serializer = DriverLocationSerializer(location)

        return Response(serializer.data)

class NearbyDriversView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        lat = float(request.query_params.get("lat"))
        lng = float(request.query_params.get("lng"))

        point = Point(lng, lat)

        drivers = (
            DriverLocation.objects
            .annotate(distance=Distance("location", point))
            .filter(
                location__distance_lte=(point, D(km=10)),
                driver__is_available=True
            )
            .order_by("distance")[:10]
        )

        serializer = DriverLocationSerializer(drivers, many=True)

        return Response(serializer.data)