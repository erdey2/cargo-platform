from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics, permissions, status
from .serializers import RegisterSerializer, ProfileSerializer, CustomerRegisterSerializer, DriverRegisterSerializer
from ..models import Profile


@extend_schema(
    tags=["Authentication"],
    summary="Register user",
    description="Create a new user account.",
    request=RegisterSerializer,
    responses={201: RegisterSerializer},
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


@extend_schema(tags=["Profiles"])
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.profile

    @extend_schema(
        summary="Get my profile",
        description="Retrieve the profile of the currently authenticated user.",
        responses={200: ProfileSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update my profile",
        description="Update the profile of the current user.",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update my profile",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

@extend_schema(tags=["Profiles"])
class ProfileListView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Profile.objects.all()

    @extend_schema(
        summary="List all profiles (Admin)",
        description="Retrieve all user profiles.",
        responses={200: ProfileSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

@extend_schema(
    tags=["Authentication"],
    summary="Customer Registration",
    description="Register a new customer account.",
    request=CustomerRegisterSerializer,
    responses={201: {"type": "object", "properties": {"message": {"type": "string"}}}},
)
class CustomerRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(request=request)
            return Response(
                {"message": "Customer registered successfully"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=["Authentication"],
    summary="Driver Registration",
    description="Register a new driver with profile, driver info, and vehicle.",
    request=DriverRegisterSerializer,
    responses={201: {"type": "object", "properties": {"message": {"type": "string"}}}},
    examples=[
        OpenApiExample(
            "Driver Registration Example",
            value={
                "email": "driver1@example.com",
                "password1": "Driver@12345",
                "password2": "Driver@12345",
                "full_name": "Abel Tesfaye",
                "phone": "+251911000001",
                "address": "Addis Ababa",
                "city": "Addis Ababa",
                "country": "Ethiopia",
                "latitude_input": 9.0054,
                "longitude_input": 38.7615,
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
        serializer = DriverRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(request=request)
            return Response(
                {"message": "Driver registered successfully"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)