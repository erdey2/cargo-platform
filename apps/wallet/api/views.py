from decimal import Decimal, InvalidOperation
import uuid

from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter

from apps.wallet.models import DriverWallet, WalletTransaction, DriverPayout
from apps.wallet.api.serializers import WalletTransactionSerializer

MIN_PAYOUT_AMOUNT = Decimal("100")

def get_driver(user):
    if not hasattr(user, "driverprofile"):
        raise ValidationError("Driver profile not found")
    return user.driverprofile

# Wallet
@extend_schema(
    tags=["Wallet"],
    summary="Get driver wallet balance",
)
class DriverWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = get_driver(request.user)
        wallet, _ = DriverWallet.objects.get_or_create(driver=driver)

        return Response({"balance": str(wallet.balance)})

@extend_schema(
    tags=["Wallet"],
    summary="List wallet transactions",
)
class WalletTransactionListView(ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        driver = get_driver(self.request.user)

        return WalletTransaction.objects.filter(
            wallet__driver=driver
        ).order_by("-created_at")

# Payout Request
@extend_schema(
    tags=["Payouts"],
    summary="Request payout"
)
class RequestPayoutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        driver = get_driver(request.user)

        idempotency_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4())

        existing = DriverPayout.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.driver != driver:
                raise ValidationError("Idempotency key already used by another driver")

            return Response({
                "message": "Duplicate request",
                "payout_id": existing.id,
                "status": existing.status
            })

        try:
            amount = Decimal(str(request.data.get("amount")))
        except:
            raise ValidationError("Invalid amount")

        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")

        if amount < MIN_PAYOUT_AMOUNT:
            raise ValidationError("Minimum payout is 100")

        wallet = DriverWallet.objects.select_for_update().get(driver=driver)

        if wallet.balance < amount:
            raise ValidationError("Insufficient balance")

        if DriverPayout.objects.filter(
            driver=driver,
            status__in=[
                DriverPayout.Status.PENDING,
                DriverPayout.Status.PROCESSING
            ]
        ).exists():
            raise ValidationError("Active payout already exists")

        payout = DriverPayout.objects.create(
            driver=driver,
            amount=amount,
            idempotency_key=idempotency_key,
            status=DriverPayout.Status.PENDING
        )

        return Response({
            "message": "Payout requested",
            "payout_id": payout.id
        })

class ApprovePayoutView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, payout_id):

        payout = get_object_or_404(
            DriverPayout.objects.select_for_update(),
            id=payout_id
        )

        if payout.status != DriverPayout.Status.PENDING:
            raise ValidationError("Invalid state transition")

        wallet = DriverWallet.objects.select_for_update().get(driver=payout.driver)

        if wallet.balance < payout.amount:
            raise ValidationError("Insufficient balance")

        payout.status = DriverPayout.Status.PROCESSING
        payout.save(update_fields=["status"])

        wallet.balance -= payout.amount
        wallet.save(update_fields=["balance"])

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=payout.amount,
            gross_amount=payout.amount,
            type=WalletTransaction.Type.DEBIT,
            reference=f"payout_{payout.id}",
            description="Withdrawal"
        )

        payout.status = DriverPayout.Status.APPROVED
        payout.processed_at = timezone.now()
        payout.save(update_fields=["status", "processed_at"])

        return Response({"message": "Payout approved"})

class RejectPayoutView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, payout_id):

        payout = get_object_or_404(
            DriverPayout.objects.select_for_update(),
            id=payout_id
        )

        if payout.status != DriverPayout.Status.PENDING:
            raise ValidationError("Payout already processed")

        payout.status = DriverPayout.Status.REJECTED
        payout.processed_at = timezone.now()
        payout.save(update_fields=["status", "processed_at"])

        return Response({"message": "Payout rejected"})