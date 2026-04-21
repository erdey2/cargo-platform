from rest_framework import serializers
from ..models import Assignment
from apps.shipments.api.serializers import ShipmentSimpleSerializer
from apps.drivers.api.serializers import DriverSimpleSerializer
from apps.vehicles.api.serializers import VehicleSimpleSerializer

class AssignmentSerializer(serializers.ModelSerializer):
    shipment = ShipmentSimpleSerializer(read_only=True)
    driver = DriverSimpleSerializer(read_only=True)
    vehicle = VehicleSimpleSerializer(read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "id",
            "shipment",
            "driver",
            "vehicle",
            "status",
            "accepted_at",
            "picked_up_at",
            "delivered_at",
            "created_at",
        ]

class AssignmentStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ["status"]