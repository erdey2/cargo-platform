from django.db import IntegrityError, transaction

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.rating.api.serializers import RatingCreateSerializer, RatingSerializer


@extend_schema(tags=["Ratings"])
class CreateRatingView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Rate a driver after delivery",
        description=(
            "Customers can rate the driver of a shipment only after the shipment "
            "has been delivered or completed. One rating per shipment is allowed."
        ),
        request=RatingCreateSerializer,
        responses={201: RatingSerializer, 400: OpenApiResponse(description="Validation error")},
    )
    @transaction.atomic
    def post(self, request):
        serializer = RatingCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            rating = serializer.save()
        except IntegrityError:
            raise ValidationError({"shipment_id": "This shipment has already been rated."})
        return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)


