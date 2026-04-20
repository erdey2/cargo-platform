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
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@extend_schema(
    tags=["Driver Location"],
    summary="Update driver location (Real-time)",
    description="""
Driver sends live GPS coordinates.

### What happens:
- Saves driver location in database
- Marks driver as online
- Broadcasts location to:
  - Customer (tracking screen)
  - Admin (dashboard)
  - Driver (optional confirmation)

### Used for:
real-time tracking
""",
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
    responses={
        200: OpenApiResponse(
            response=DriverLocationSerializer,
            description="Location updated and broadcasted successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "driver": 5,
                        "location": {
                            "lat": 9.03,
                            "lng": 38.74
                        },
                        "heading": 90,
                        "speed": 60,
                        "is_online": True
                    }
                )
            ]
        )
    }
)
class UpdateDriverLocationView(APIView):
    permission_classes = [IsAuthenticated, IsDriver]

    def post(self, request):

        driver = DriverProfile.objects.filter(user=request.user).first()
        if not driver:
            raise ValidationError("Driver profile not found.")

        lat = request.data.get("lat")
        lng = request.data.get("lng")

        if lat is None or lng is None:
            raise ValidationError("Latitude and longitude are required.")

        lat = float(lat)
        lng = float(lng)

        location = Point(lng, lat, srid=4326)

        # SAVE DRIVER LOCATION (DB)
        driver_location, _ = DriverLocation.objects.update_or_create(
            driver=driver,
            defaults={
                "location": location,
                "heading": request.data.get("heading"),
                "speed": request.data.get("speed"),
                "is_online": True,
            }
        )

        # FIND ACTIVE SHIPMENT
        shipment = Shipment.objects.filter(
            driver=driver,
            status="assigned"
        ).first()

        # REAL-TIME BROADCAST
        if shipment:
            channel_layer = get_channel_layer()

            payload = {
                "type": "send_location",
                "payload": {
                    "event": "driver.location",
                    "data": {
                        "driver_id": driver.id,
                        "shipment_id": shipment.id,
                        "lat": lat,
                        "lng": lng,
                        "heading": request.data.get("heading"),
                        "speed": request.data.get("speed"),
                    }
                }
            }

            # CUSTOMER TRACKING
            async_to_sync(channel_layer.group_send)(
                f"shipment_{shipment.id}_customer",
                payload
            )

            # ADMIN TRACKING
            async_to_sync(channel_layer.group_send)(
                f"shipment_{shipment.id}_admin",
                payload
            )

            # DRIVER (optional sync confirmation)
            async_to_sync(channel_layer.group_send)(
                f"shipment_{shipment.id}_driver",
                payload
            )

        return Response(DriverLocationSerializer(driver_location).data)

@extend_schema(tags=["Driver Location"])
class DriverLocationView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Driver Location"],
        summary="Get driver current location",
        description="Retrieve latest GPS position of a driver.",
        parameters=[
            OpenApiParameter(
                name="driver_id",
                description="Driver ID",
                required=True,
                type=int,
                location="path",
            )
        ],
        responses={
            200: OpenApiResponse(
                response=DriverLocationSerializer,
                description="Driver location retrieved"
            )
        },
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
        tags=["Driver Location"],
        summary="Find nearby drivers",
        description="""
    Find drivers within 10km radius.

    ### Filters:
    - Only online drivers
    - Only available drivers

    ### Sorting:
    - By distance (closest first)
    - Then by rating
    """,
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
        responses={
            200: OpenApiResponse(
                response=DriverLocationSerializer(many=True),
                description="List of nearby drivers"
            )
        },
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

class TrackingWebSocketDocs(APIView):

    @extend_schema(
        tags=["WebSocket - Tracking"],
        operation_id="shipment_tracking_websocket",
        summary="Real-time Shipment Tracking WebSocket",
        description="""
### Shipment Tracking WebSocket API
This WebSocket enables real-time tracking of shipments between drivers, customers, and admins.

---
### Connection URL
`wss://cargo-platform.onrender.com/ws/shipment/{shipment_id}/?token=ACCESS_TOKEN`
---

### Roles & Capabilities
| Role | Capabilities |
| Driver | Sends live GPS updates (every 2–5 seconds) |
| Customer | Receives real-time updates for their specific shipment |
| Admin | Receives all tracking updates for monitoring purposes |

### Event-Driven Flow
1. Client → Server (Driver Only): Driver sends location JSON.
2. Server → Clients (Broadcast): System broadcasts updates to the Customer and Admin.
        """,
        parameters=[
            OpenApiParameter(
                name="shipment_id",
                type=int,
                location="path",
                description="The unique ID of the shipment to track.",
                required=True
            ),
            OpenApiParameter(
                name="token",
                type=str,
                location="query",
                description="JWT Access Token for authentication.",
                required=True
            ),
        ],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "format": "float", "example": 9.03},
                    "lng": {"type": "number", "format": "float", "example": 38.74},
                    "heading": {"type": "number", "format": "float", "example": 90, "nullable": True},
                    "speed": {"type": "number", "format": "float", "example": 60, "nullable": True}
                },
                "required": ["lat", "lng"]
            }
        },
        responses={
            101: OpenApiResponse(
                description="Switching Protocols - WebSocket connection established.",
                examples=[
                    OpenApiExample(
                        name="Driver Location Broadcast (Server -> Client)",
                        value={
                            "event": "driver.location",
                            "data": {
                                "driver_id": 5,
                                "shipment_id": 63,
                                "lat": 9.03,
                                "lng": 38.74,
                                "heading": 90,
                                "speed": 60,
                                "timestamp": "2026-04-20T17:08:00Z"
                            }
                        }
                    )
                ],
            )
        },
        examples=[
            OpenApiExample(
                name="Driver Sending GPS Update (Client -> Server)",
                value={
                    "lat": 9.03,
                    "lng": 38.74,
                    "heading": 90,
                    "speed": 60
                },
                request_only=True,
            ),
        ],
    )
    def get(self, request, shipment_id=None):
        """
        Dummy endpoint used only for OpenAPI/Swagger documentation.
        """
        return Response({
            "message": "This is a documentation-only endpoint for the Tracking WebSocket. Use the wss:// protocol to connect."
        })