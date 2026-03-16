from django.db import models
from core.models import BaseModel


class PricingRule(BaseModel):

    vehicle_type = models.CharField(max_length=50)

    base_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    per_km_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    per_kg_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
