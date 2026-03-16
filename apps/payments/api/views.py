from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.shipments.models import Shipment
from ..models import Transaction

class CreatePaymentView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, shipment_id):

        shipment = Shipment.objects.get(id=shipment_id)

        transaction = Transaction.objects.create(
            shipment=shipment,
            amount=shipment.final_price,
            payment_method=request.data["payment_method"]
        )

        return Response({"transaction_id": transaction.id })