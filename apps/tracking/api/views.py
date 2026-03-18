from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, ValidationError
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from ..models import DriverLocation
from .serializers import DriverLocationSerializer
from apps.drivers.models import DriverProfile
from core.permissions import IsDriver


class UpdateDriverLocationView(APIView):

    permission_classes = [IsAuthenticated, IsDriver]

    def post(self, request):

        try:
            driver = DriverProfile.objects.get(user=request.user)
        except DriverProfile.DoesNotExist:
            raise ValidationError("Driver profile not found.")

        # Validate input
        lat = request.data.get("lat")
        lng = request.data.get("lng")

        if lat is None or lng is None:
            raise ValidationError("Latitude and longitude are required.")

        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            raise ValidationError("Invalid latitude or longitude format.")

        # Correct GeoDjango order: (longitude, latitude)
        location = Point(lng, lat)

        driver_location, _ = DriverLocation.objects.update_or_create(
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

        try:
            location = DriverLocation.objects.get(driver_id=driver_id)
        except DriverLocation.DoesNotExist:
            raise NotFound("Driver location not found.")

        serializer = DriverLocationSerializer(location)
        return Response(serializer.data)

class NearbyDriversView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        if lat is None or lng is None:
            raise ValidationError("lat and lng are required.")

        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            raise ValidationError("Invalid latitude or longitude.")

        point = Point(lng, lat)

        drivers = (
            DriverLocation.objects
            .annotate(distance=Distance("location", point))
            .filter(
                location__distance_lte=(point, D(km=10)),
                driver__is_available=True,
                is_online=True
            )
            .order_by("distance")[:10]
        )

        serializer = DriverLocationSerializer(drivers, many=True)
        return Response(serializer.data)