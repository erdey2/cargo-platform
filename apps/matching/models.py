from django.db import models
from django.utils import timezone
from core.models import BaseModel


class DriverOffer(BaseModel):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    shipment = models.ForeignKey(
        "shipments.Shipment",
        on_delete=models.CASCADE,
        related_name="offers"
    )

    driver = models.ForeignKey(
        "drivers.DriverProfile",
        on_delete=models.CASCADE,
        related_name="offers"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True
    )

    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["shipment", "status", "expires_at"]),
        ]
        unique_together = ("shipment", "driver")
