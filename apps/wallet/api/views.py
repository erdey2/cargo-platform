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

from apps.wallet.models import DriverWallet, WalletTransaction, DriverPayout
from apps.wallet.api.serializers import WalletTransactionSerializer

# Business rule
MIN_PAYOUT_AMOUNT = Decimal("100")

class DriverWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "driverprofile"):
            raise ValidationError("Driver profile not found")

        driver = request.user.driverprofile
        wallet, _ = DriverWallet.objects.get_or_create(driver=driver)

        return Response({
            "balance": str(wallet.balance)
        })

class WalletTransactionListView(ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, "driverprofile"):
            raise ValidationError("Driver profile not found")

        driver = self.request.user.driverprofile

        return WalletTransaction.objects.filter(
            wallet__driver=driver
        ).order_by("-created_at")

class RequestPayoutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        if not hasattr(request.user, "driverprofile"):
            raise ValidationError("Driver profile not found")

        driver = request.user.driverprofile

        # Idempotency key from client (or generate)
        idempotency_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4())

        # Prevent duplicate request
        existing = DriverPayout.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return Response({
                "message": "Duplicate request",
                "payout_id": existing.id,
                "status": existing.status
            })

        # Validate amount
        try:
            amount = Decimal(str(request.data.get("amount")))
        except (InvalidOperation, TypeError):
            raise ValidationError("Invalid amount format")

        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")

        if amount < MIN_PAYOUT_AMOUNT:
            raise ValidationError(f"Minimum payout is {MIN_PAYOUT_AMOUNT}")

        wallet, _ = DriverWallet.objects.select_for_update().get_or_create(driver=driver)

        if wallet.balance < amount:
            raise ValidationError("Insufficient balance")

        if DriverPayout.objects.filter(driver=driver, status__in=["pending", "processing"]).exists():
            raise ValidationError("You already have an active payout request")

        payout = DriverPayout.objects.create(
            driver=driver,
            amount=amount,
            status="pending",
            idempotency_key=idempotency_key
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

        if payout.status != "pending":
            raise ValidationError("Payout already processed")

        # Move to processing first
        payout.status = "processing"
        payout.save(update_fields=["status"])

        wallet = DriverWallet.objects.select_for_update().get(driver=payout.driver)

        if wallet.balance < payout.amount:
            raise ValidationError("Insufficient balance")

        # Deduct balance
        wallet.balance -= payout.amount
        wallet.save(update_fields=["balance"])

        # Record transaction
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=payout.amount,
            type="debit",
            reference=f"payout_{payout.id}",
            description="Withdrawal"
        )

        # Finalize payout
        payout.status = "approved"
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

        if payout.status != "pending":
            raise ValidationError("Payout already processed")

        payout.status = "rejected"
        payout.processed_at = timezone.now()
        payout.save(update_fields=["status", "processed_at"])

        return Response({"message": "Payout rejected"})