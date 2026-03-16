from core.models import BaseModel
from django.db import models
from django.contrib.gis.db import models as gis_models
from apps.users.models import User


class Shipment(BaseModel):

    STATUS_CHOICES = (
        ("created", "Created"),
        ("matching", "Matching"),
        ("assigned", "Assigned"),
        ("cancelled", "Cancelled"),
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shipments",
        db_index=True
    )

    pickup_address = models.CharField(max_length=255)
    dropoff_address = models.CharField(max_length=255)

    pickup_location = gis_models.PointField(geography=True)
    dropoff_location = gis_models.PointField(geography=True)

    weight = models.FloatField()
    volume = models.FloatField()

    cargo_type = models.ForeignKey(
        "CargoType",
        on_delete=models.SET_NULL,
        null=True,
        related_name="shipments"
    )

    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created",
        db_index=True
    )

    estimated_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Shipment {self.id}"

class CargoType(models.Model):

    name = models.CharField(max_length=100, unique=True)

    requires_special_vehicle = models.BooleanField(default=False)

    fragile = models.BooleanField(default=False)

    hazardous = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class ShipmentStatusHistory(BaseModel):

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="status_history"
    )

    status = models.CharField(
        max_length=20,
        choices=Shipment.STATUS_CHOICES
    )

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="shipment_changes"
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shipment"])
        ]