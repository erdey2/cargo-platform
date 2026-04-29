from django.db import models
from apps.users.models import User
from core.models import BaseModel
from apps.shipments.models import Shipment


class Rating(BaseModel):

    shipment = models.OneToOneField(Shipment, on_delete=models.CASCADE)

    driver = models.ForeignKey(
        "drivers.DriverProfile",
        on_delete=models.CASCADE,
        related_name="driver_ratings"
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    score = models.IntegerField()

    comment = models.TextField(blank=True)
