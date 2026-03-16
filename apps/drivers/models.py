from django.db import models
from apps.users.models import User
from core.models import BaseModel
from apps.shipments.models import Shipment

class DriverProfile(BaseModel):

    VERIFICATION_STATUS = (
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    national_id = models.CharField(max_length=100)

    driver_license = models.CharField(max_length=100)
    license_expiry = models.DateField()

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default="pending"
    )

    rating = models.FloatField(default=5.0)

    total_trips = models.IntegerField(default=0)

    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"Driver {self.user.username}"


class DriverDocument(BaseModel):

    DOCUMENT_TYPES = (
        ("license", "Driver License"),
        ("insurance", "Insurance"),
        ("national_id", "National ID"),
    )

    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE
    )

    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPES
    )

    file = models.FileField(upload_to="driver_documents/")

    is_verified = models.BooleanField(default=False)

class DriverEarning(BaseModel):

    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE
    )

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    paid = models.BooleanField(default=False)
