from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.rating.api.serializers import RatingCreateSerializer, RatingSerializer
from ..models import Rating
from ..services import RatingService

@extend_schema(tags=["Ratings"])
class CreateRatingView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Rate a driver after delivery",
        description="""
Customers can rate the driver of a shipment only after delivery/completion.

Rules:
- Only customer who created shipment can rate
- Only after delivered/completed
- Only one rating per shipment
""",
        request=RatingCreateSerializer,
        responses={
            201: RatingSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = RatingCreateSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        try:
            rating = serializer.save()
        except IntegrityError:
            raise ValidationError({
                "shipment_id": "This shipment has already been rated."
            })

        RatingService.update_driver_rating(
            driver=rating.driver,
            new_score=rating.score
        )

        return Response(
            RatingSerializer(rating).data,
            status=status.HTTP_201_CREATED
        )

@extend_schema(
    tags=["Ratings"],
    summary="List ratings",
    description="""
Retrieve ratings for the authenticated user.

Optional filters:
- ?driver_id=ID
- ?shipment_id=ID
"""
)
class RatingListView(ListAPIView):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Rating.objects.select_related(
            "shipment",
            "driver",
            "customer"
        ).order_by("-created_at")

        driver_id = self.request.query_params.get("driver_id")
        shipment_id = self.request.query_params.get("shipment_id")

        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)

        if shipment_id:
            queryset = queryset.filter(shipment_id=shipment_id)

        # limit to user's data
        return queryset.filter(customer=user)

@extend_schema(
    tags=["Ratings"],
    summary="Driver ratings",
    description="Get ratings received by the authenticated driver"
)
class DriverRatingView(ListAPIView):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, "driverprofile"):
            raise ValidationError("Driver profile not found")

        driver = self.request.user.driverprofile

        return Rating.objects.filter(
            driver=driver
        ).select_related("shipment", "customer").order_by("-created_at")

class DriverAverageRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "driverprofile"):
            raise ValidationError("Driver profile not found")

        driver = request.user.driverprofile

        return Response({
            "average_rating": str(driver.average_rating),
            "total_ratings": driver.total_ratings
        })