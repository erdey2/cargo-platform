from django.db import models
from core.models import BaseModel
from apps.shipments.models import Shipment

class Transaction(BaseModel):

    PAYMENT_METHODS = (
        ("cash", "Cash"),
        ("mobile_money", "Mobile Money"),
        ("card", "Card"),
    )

    shipment = models.OneToOneField(
        Shipment,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS
    )

    status = models.CharField(
        max_length=20,
        default="pending"
    )
