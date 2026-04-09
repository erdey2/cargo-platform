from rest_framework import serializers
from ..models import Assignment

class AssignmentSerializer(serializers.ModelSerializer):

    shipment_id = serializers.ReadOnlyField(source="shipment.id")
    driver_id = serializers.ReadOnlyField(source="driver.id")
    vehicle_id = serializers.ReadOnlyField(source="vehicle.id")

    class Meta:
        model = Assignment
        fields = [
            "id",
            "shipment_id",
            "driver_id",
            "vehicle_id",
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