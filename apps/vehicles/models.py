from django.db import models
from core.models import BaseModel
from apps.drivers.models import DriverProfile


class VehicleType(models.Model):
    name = models.CharField(max_length=100, unique=True) # Motorcycle, Pickup, Mini Truck, Large Truck
    max_weight = models.FloatField()
    max_volume = models.FloatField()
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Vehicle(BaseModel):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name="vehicles")
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    plate_number = models.CharField(max_length=20, unique=True)
    capacity_weight = models.FloatField()
    capacity_volume = models.FloatField()
    verification_status = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["driver"]),
            models.Index(fields=["capacity_weight"]),
            models.Index(fields=["capacity_volume"]),
        ]

    def __str__(self):
        return f"{self.vehicle_type} - {self.plate_number}  - {self.driver}"

class VehicleDocument(BaseModel):
    vehicle = models.ForeignKey (Vehicle, on_delete=models.CASCADE, related_name="documents")
    document_name = models.CharField(max_length=100)
    file = models.FileField(upload_to="vehicle_documents/")
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.document_name

