from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.wallet.models import DriverWallet, WalletTransaction, DriverPayout
from apps.wallet.api.serializers import WalletTransactionSerializer


class DriverWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = request.user.driverprofile
        wallet, _ = DriverWallet.objects.get_or_create(driver=driver)

        return Response({
            "balance": str(wallet.balance)
        })

class WalletTransactionListView(ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        driver = self.request.user.driverprofile
        return WalletTransaction.objects.filter(
            wallet__driver=driver
        ).order_by("-created_at")

class RequestPayoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        driver = request.user.driverprofile
        amount = request.data.get("amount")

        wallet = DriverWallet.objects.get(driver=driver)

        if wallet.balance < float(amount):
            raise ValidationError("Insufficient balance")

        payout = DriverPayout.objects.create(
            driver=driver,
            amount=amount
        )

        return Response({"message": "Payout requested"})

class ApprovePayoutView(APIView):
    permission_classes = [IsAuthenticated]  # add admin check

    @transaction.atomic
    def post(self, request, payout_id):

        payout = DriverPayout.objects.select_for_update().get(id=payout_id)
        wallet = DriverWallet.objects.select_for_update().get(driver=payout.driver)

        if wallet.balance < payout.amount:
            raise ValidationError("Insufficient balance")

        wallet.balance -= payout.amount
        wallet.save(update_fields=["balance"])

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=payout.amount,
            type="debit",
            reference=f"payout_{payout.id}",
            description="Withdrawal"
        )

        payout.status = "approved"
        payout.processed_at = timezone.now()
        payout.save()

        return Response({"message": "Payout approved"})