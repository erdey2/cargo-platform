from django.contrib.gis.geos import Point
from rest_framework import serializers
from ..models import Shipment, CargoType, ShipmentStatusHistory

class CargoTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoType
        fields = "__all__"

class ShipmentSerializer(serializers.ModelSerializer):
    customer = serializers.ReadOnlyField(source="customer.id")

    # Write-only inputs
    pickup_lat = serializers.FloatField(write_only=True)
    pickup_lng = serializers.FloatField(write_only=True)
    dropoff_lat = serializers.FloatField(write_only=True)
    dropoff_lng = serializers.FloatField(write_only=True)

    pickup_latitude = serializers.SerializerMethodField()
    pickup_longitude = serializers.SerializerMethodField()
    dropoff_latitude = serializers.SerializerMethodField()
    dropoff_longitude = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            "id",
            "customer",
            "pickup_address",
            "dropoff_address",

            # input
            "pickup_lat",
            "pickup_lng",
            "dropoff_lat",
            "dropoff_lng",

            # output
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",

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
            "estimated_price",
            "final_price",
        ]

    def get_pickup_latitude(self, obj):
        return obj.pickup_location.y if obj.pickup_location else None

    def get_pickup_longitude(self, obj):
        return obj.pickup_location.x if obj.pickup_location else None

    def get_dropoff_latitude(self, obj):
        return obj.dropoff_location.y if obj.dropoff_location else None

    def get_dropoff_longitude(self, obj):
        return obj.dropoff_location.x if obj.dropoff_location else None

    def validate(self, data):
        if data["weight"] <= 0:
            raise serializers.ValidationError("Weight must be positive")

        if data["volume"] <= 0:
            raise serializers.ValidationError("Volume must be positive")

        lat = data.get("pickup_lat")
        lng = data.get("pickup_lng")

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise serializers.ValidationError("Invalid pickup coordinates")

        return data

    def create(self, validated_data):
        pickup = Point(
            validated_data.pop("pickup_lng"),
            validated_data.pop("pickup_lat"),
        )
        dropoff = Point(
            validated_data.pop("dropoff_lng"),
            validated_data.pop("dropoff_lat"),
        )

        if pickup == dropoff:
            raise serializers.ValidationError(
                "Pickup and dropoff cannot be the same location"
            )

        return Shipment.objects.create(
            pickup_location=pickup,
            dropoff_location=dropoff,
            **validated_data
        )

class ShipmentStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentStatusHistory
        fields = "__all__"