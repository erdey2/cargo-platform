import uuid
from django.db import models


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.CharField(max_length=100)
    zone = models.CharField(max_length=100, blank=True, null=True)
    woreda = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    latitude = models.FloatField()
    longitude = models.FloatField()

    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.city} - {self.region}"
