from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiExample
from .serializers import DriverRegistrationSerializer

@extend_schema(
    request=DriverRegistrationSerializer,
    responses={201: {"type": "object", "properties": {"message": {"type": "string"}}}},
    description="Register a new driver with profile, driver info, and vehicle",
    examples=[
        OpenApiExample(
            "Driver Registration Example",
            value={
                "email": "driver1@example.com",
                "password": "Driver@12345",
                "full_name": "Abel Tesfaye",
                "phone": "+251911000001",
                "address": "Addis Ababa",
                "city": "Addis Ababa",
                "location": "38.7615 9.0054",
                "national_id": "NID-12345",
                "driver_license": "LIC-12345",
                "vehicle": {
                    "plate_number": "AA-12345",
                    "vehicle_type": 1
                }
            },
            request_only=True
        )
    ]
)
class DriverRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DriverRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Driver registered successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)