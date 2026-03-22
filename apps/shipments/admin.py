from django.contrib import admin
from .models import CargoType, Shipment, ShipmentStatusHistory

admin.site.register(CargoType)
admin.site.register(Shipment)
admin.site.register(ShipmentStatusHistory)
