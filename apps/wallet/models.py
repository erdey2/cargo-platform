from django.db import models
from apps.drivers.models import DriverProfile
from core.models import BaseModel


class DriverWallet(BaseModel):
    driver = models.OneToOneField(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.driver.user.username} Wallet"


class WalletTransaction(BaseModel):

    TRANSACTION_TYPE = (
        ("credit", "Credit"),
        ("debit", "Debit"),
    )

    wallet = models.ForeignKey(
        DriverWallet,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)

    reference = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.type} - {self.amount}"


class DriverPayout(BaseModel):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="payouts"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout {self.id} - {self.status}"
