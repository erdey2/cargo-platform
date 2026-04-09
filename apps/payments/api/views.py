from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, ValidationError
from apps.shipments.models import Shipment
from ..models import Transaction
from .serializers import CreatePaymentSerializer

class CreatePaymentView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Payments"],
        summary="Create payment for a shipment",
        description="""
            This endpoint allows a user to create a payment for a specific shipment.

            Rules:
            - Only the shipment owner or admin can create payment
            - Shipment must have a final price
            - Payment must not already exist
            """,

        request=CreatePaymentSerializer,

        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },

        parameters=[
            OpenApiParameter(
                name="shipment_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="ID of the shipment to pay for",
                required=True,
            )
        ],

        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "payment_method": "telebirr"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "transaction_id": 12,
                    "status": "pending"
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Already Paid",
                value={
                    "detail": "Payment already exists for this shipment"
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, shipment_id):
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            shipment = Shipment.objects.get(id=shipment_id)
        except Shipment.DoesNotExist:
            raise NotFound("Shipment not found")

        if shipment.customer_id != request.user.id and not request.user.is_staff:
            raise ValidationError("You can only pay for your own shipment")

        if shipment.final_price is None:
            raise ValidationError("Shipment final price is not available yet")

        if Transaction.objects.filter(shipment=shipment).exists():
            raise ValidationError("Payment already exists for this shipment")

        transaction = Transaction.objects.create(
            shipment=shipment,
            amount=shipment.final_price,
            payment_method=serializer.validated_data["payment_method"],
        )

        return Response({"transaction_id": transaction.id, "status": transaction.status})