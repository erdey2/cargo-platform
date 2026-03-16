from rest_framework import serializers
from ..models import Shipment, CargoType, ShipmentStatusHistory

class CargoTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = CargoType
        fields = "__all__"

class ShipmentSerializer(serializers.ModelSerializer):

    customer = serializers.ReadOnlyField(source="customer.id")

    class Meta:
        model = Shipment
        fields = [
            "id",
            "customer",
            "pickup_address",
            "dropoff_address",
            "pickup_location",
            "dropoff_location",
            "weight",
            "volume",
            "cargo_type",
            "description",
            "status",
            "estimated_price",
            "final_price",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "created_at",
        ]
        read_only_fields = [
            "status",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "final_price",
        ]

class ShipmentStatusHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = ShipmentStatusHistory
        fields = "__all__"