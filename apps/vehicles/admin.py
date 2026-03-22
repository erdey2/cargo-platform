from django.contrib import admin
from .models import VehicleType, Vehicle, VehicleDocument

admin.site.register(VehicleType)
admin.site.register(Vehicle)
admin.site.register(VehicleDocument)
