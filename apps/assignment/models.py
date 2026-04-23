from django.db import models
from core.models import BaseModel

class Assignment(BaseModel):

    STATUS_CHOICES = [
        ("assigned", "Assigned"),
        ("driver_arriving", "Driver Arriving"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    shipment = models.OneToOneField(
        "shipments.Shipment",
        on_delete=models.CASCADE,
        related_name="assignment"
    )

    driver = models.ForeignKey(
        "drivers.DriverProfile",
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="assigned",
        db_index=True
    )

    accepted_at = models.DateTimeField(auto_now_add=True)

    picked_up_at = models.DateTimeField(null=True, blank=True)

    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Shipment {self.shipment_id} → Driver {self.driver_id}"