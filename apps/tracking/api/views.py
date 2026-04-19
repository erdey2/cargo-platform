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
from apps.shipments.models import Shipment
from core.permissions import IsDriver
from drf_spectacular.utils import extend_schema, OpenApiParameter
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@extend_schema(tags=["Driver Location"])
class UpdateDriverLocationView(APIView):

    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(
        summary="Update driver location",
        description=(
            "Update the current location of the authenticated driver.\n\n"
            "This will:\n"
            "- Validate latitude and longitude\n"
            "- Update or create driver location\n"
            "- Mark driver as online\n"
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "example": 9.03},
                    "lng": {"type": "number", "example": 38.74},
                    "heading": {"type": "number", "example": 90},
                    "speed": {"type": "number", "example": 60},
                },
                "required": ["lat", "lng"],
            }
        },
        responses={200: DriverLocationSerializer},
    )
    def post(self, request):

        driver = DriverProfile.objects.filter(user=request.user).first()
        if not driver:
            raise ValidationError("Driver profile not found.")

        lat = request.data.get("lat")
        lng = request.data.get("lng")

        if lat is None or lng is None:
            raise ValidationError("Latitude and longitude are required.")

        lat, lng = float(lat), float(lng)

        location = Point(lng, lat, srid=4326)

        driver_location, _ = DriverLocation.objects.update_or_create(
            driver=driver,
            defaults={
                "location": location,
                "heading": request.data.get("heading"),
                "speed": request.data.get("speed"),
                "is_online": True
            }
        )

        # REAL-TIME SEND
        shipment = Shipment.objects.filter(
            driver=driver,
            status="assigned"
        ).first()

        if shipment:
            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f"shipment_{shipment.id}",
                {
                    "type": "driver_location",
                    "data": {
                        "type": "driver_location",
                        "driver_id": driver.id,
                        "lat": lat,
                        "lng": lng,
                        "heading": request.data.get("heading"),
                        "speed": request.data.get("speed"),
                    }
                }
            )

        return Response(DriverLocationSerializer(driver_location).data)

@extend_schema(tags=["Driver Location"])
class DriverLocationView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get driver location",
        description="Retrieve the current location of a specific driver.",
        parameters=[
            OpenApiParameter(
                name="driver_id",
                description="ID of the driver",
                required=True,
                type=int,
                location="path",
            )
        ],
        responses={200: DriverLocationSerializer},
    )
    def get(self, request, driver_id):

        try:
            location = DriverLocation.objects.get(driver_id=driver_id)
        except DriverLocation.DoesNotExist:
            raise NotFound("Driver location not found.")

        serializer = DriverLocationSerializer(location)
        return Response(serializer.data)

@extend_schema(tags=["Driver Location"])
class NearbyDriversView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Find nearby drivers",
        description=(
            "Find drivers within a 10km radius from a given location.\n\n"
            "Filters:\n"
            "- Only available drivers\n"
            "- Only online drivers\n"
            "- Sorted by distance\n"
            "- Maximum 10 drivers returned"
        ),
        parameters=[
            OpenApiParameter(
                name="lat",
                description="Latitude",
                required=True,
                type=float,
                location="query",
            ),
            OpenApiParameter(
                name="lng",
                description="Longitude",
                required=True,
                type=float,
                location="query",
            ),
        ],
        responses={200: DriverLocationSerializer(many=True)},
    )
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

        point = Point(lng, lat, srid=4326)

        drivers = (
            DriverLocation.objects
            .annotate(distance=Distance("location", point, spheroid=True))
            .filter(
                location__distance_lte=(point, D(km=10)),
                driver__is_available=True,
                is_online=True
            )
            .order_by("distance", "-driver__rating")[:10]
        )

        serializer = DriverLocationSerializer(drivers, many=True)
        return Response(serializer.data)