from django.utils import timezone
from rest_framework import serializers
from ..models import DriverOffer

class DriverPreviewSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField(source="driver.id")
    driver_email = serializers.EmailField(source="driver.user.email")
    distance_km = serializers.SerializerMethodField()

    def get_distance_km(self, obj):
        return round(obj.distance.m / 1000, 2)

class DriverOfferSerializer(serializers.ModelSerializer):
    driver_email = serializers.EmailField(source="driver.user.email", read_only=True)

    pickup_address = serializers.CharField(source="shipment.pickup_address", read_only=True)
    dropoff_address = serializers.CharField(source="shipment.dropoff_address", read_only=True)
    weight = serializers.FloatField(source="shipment.weight", read_only=True)
    volume = serializers.FloatField(source="shipment.volume", read_only=True)

    estimated_price = serializers.DecimalField(
        source="shipment.estimated_price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    time_left_seconds = serializers.SerializerMethodField()
    wait_time_seconds = serializers.SerializerMethodField()

    class Meta:
        model = DriverOffer
        fields = [
            "id",
            "shipment",
            "driver",
            "driver_email",
            "status",
            "expires_at",
            "responded_at",
            "pickup_address",
            "dropoff_address",
            "weight",
            "volume",
            "estimated_price",
            "time_left_seconds",
            "wait_time_seconds",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "shipment",
            "driver",
            "driver_email",
            "status",
            "created_at",
        ]

    def get_time_left_seconds(self, obj):
        if not obj.expires_at:
            return 0
        remaining = (obj.expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining))

    def get_wait_time_seconds(self, obj):
        """
        Total time given to the driver before expiration
        """
        if not obj.expires_at or not obj.created_at:
            return 0
        return int((obj.expires_at - obj.created_at).total_seconds() / 60)

class DriverResponseSerializer(serializers.Serializer):
    ACTION_CHOICES = (
        ("accept", "Accept"),
        ("reject", "Reject"),
    )
    action = serializers.ChoiceField(
        choices=ACTION_CHOICES,
        help_text="Action to perform: 'accept' or 'reject'"
    )