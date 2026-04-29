from django.db import models
from decimal import Decimal
from apps.drivers.models import DriverProfile
from core.models import BaseModel


class DriverWallet(BaseModel):
    driver = models.OneToOneField(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    def __str__(self):
        return f"{self.driver.user.username} Wallet"


class WalletTransaction(BaseModel):

    class Type(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    wallet = models.ForeignKey(
        DriverWallet,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)  # NET effect

    type = models.CharField(max_length=10, choices=Type.choices)

    reference = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["reference", "type"],
                name="unique_reference_type"
            )
        ]
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"{self.type} - {self.amount}"


class DriverPayout(BaseModel):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        APPROVED = "approved", "Approved"
        PAID_OUT = "paid_out", "Paid Out"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="payouts"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    idempotency_key = models.CharField(max_length=100, unique=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout {self.id} - {self.status}"