from django.contrib.gis.db import models as gis_models
from django.db import models
from core.models import BaseModel
from apps.drivers.models import DriverProfile


class DriverLocation(BaseModel):
    driver = models.OneToOneField(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="location"
    )

    location = gis_models.PointField(geography=True, spatial_index=True)
    heading = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    is_online = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["driver"]),
        ]

    def __str__(self):
        return f"{self.driver} location"


