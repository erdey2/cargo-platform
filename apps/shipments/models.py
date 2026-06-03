from core.models import BaseModel
from django.db import models
from django.contrib.gis.db import models as gis_models
from apps.users.models import User

class Shipment(BaseModel):

    STATUS_CHOICES = (
        ("created", "Created"),
        ("matching", "Matching"),
        ("assigned", "Assigned"),
        ("driver_arriving", "Driver Arriving"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("no_driver", "No Driver"),
        ("cancelled", "Cancelled"),
    )
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shipments", db_index=True)
    driver = models.ForeignKey("drivers.DriverProfile", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="shipments"
                               )
    pickup_address = models.CharField(max_length=255)
    dropoff_address = models.CharField(max_length=255)

    pickup_location = gis_models.PointField(geography=True)
    dropoff_location = gis_models.PointField(geography=True)

    weight = models.FloatField()
    volume = models.FloatField()

    cargo_type = models.ForeignKey("CargoType", on_delete=models.SET_NULL, null=True, related_name="shipments")
    description = models.TextField(blank=True)

    recipient_name = models.CharField(max_length=255, null=True, blank=True)
    recipient_phone = models.CharField(max_length=20, null=True, blank=True)
    recipient_alternate_phone = models.CharField(max_length=20, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created", db_index=True)

    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    road_distance_km = models.FloatField(null=True, blank=True)

    proof_of_delivery = models.FileField(
        upload_to="shipment_proofs/",
        null=True,
        blank=True,
    )

    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["driver", "status"]),
        ]

    def __str__(self):
        return f"Shipment {self.pk}"

class CargoType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    requires_special_vehicle = models.BooleanField(default=False)
    fragile = models.BooleanField(default=False)
    hazardous = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class ShipmentStatusHistory(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=20, choices=Shipment.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="shipment_changes")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shipment"])
        ]


class ShipmentProofOfDelivery(BaseModel):
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="proofs_of_delivery",
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_shipment_proofs",
    )
    photo = models.ImageField(upload_to="shipment_proofs/")
    image_sha256 = models.CharField(max_length=64, db_index=True)
    gps_location = gis_models.PointField(geography=True, null=True, blank=True)
    gps_accuracy_meters = models.FloatField(null=True, blank=True)
    gps_verified = models.BooleanField(default=False, db_index=True)
    gps_distance_to_dropoff_meters = models.FloatField(null=True, blank=True)
    is_duplicate = models.BooleanField(default=False, db_index=True)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicate_versions",
    )
    verification_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    customer_confirmed = models.BooleanField(default=False, db_index=True)
    customer_confirmed_at = models.DateTimeField(null=True, blank=True)
    customer_confirmation_method = models.CharField(max_length=20, blank=True, default="")
    otp_resend_count = models.IntegerField(default=0)
    last_otp_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shipment", "image_sha256"]),
            models.Index(fields=["image_sha256"]),
            models.Index(fields=["gps_verified", "is_duplicate"]),
            models.Index(fields=["shipment", "customer_confirmed"]),
        ]

    def __str__(self):
        shipment_pk = getattr(self.shipment, "pk", None)
        return f"POD #{self.pk} for Shipment {shipment_pk}"


class ShipmentPODOTP(BaseModel):
    pod = models.ForeignKey(
        ShipmentProofOfDelivery,
        on_delete=models.CASCADE,
        related_name="otps",
    )
    phone = models.CharField(max_length=30)
    code = models.CharField(max_length=10, db_index=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    used = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for POD {getattr(self.pod, 'pk', None)} -> {self.phone}"


class TwilioDeliveryReceipt(BaseModel):
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("undelivered", "Undelivered"),
        ("failed", "Failed"),
    )

    otp = models.ForeignKey(
        ShipmentPODOTP,
        on_delete=models.CASCADE,
        related_name="delivery_receipts",
    )
    message_sid = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_code = models.CharField(max_length=10, null=True, blank=True)
    error_message = models.TextField(blank=True)
    raw_webhook_data = models.JSONField(default=dict, blank=True)
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    eligible_for_retry = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["message_sid"]),
            models.Index(fields=["otp", "status"]),
        ]

    def __str__(self):
        return f"Receipt for OTP {self.otp_id}: {self.status}"
