from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, ValidationError
from apps.shipments.models import Shipment
from ..models import Transaction
from .serializers import CreatePaymentSerializer

class CreatePaymentView(APIView):

    permission_classes = [IsAuthenticated]

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