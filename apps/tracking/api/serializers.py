from rest_framework import serializers
from ..models import DriverLocation
from apps.drivers.api.serializers import DriverSimpleSerializer

class DriverLocationSerializer(serializers.ModelSerializer):
    driver = DriverSimpleSerializer(read_only=True)

    class Meta:
        model = DriverLocation
        fields = [
            "id",
            "driver",
            "location",
            "heading",
            "speed",
            "is_online",
            "last_updated"
        ]
        read_only_fields = ["id", "driver", "is_online", "last_updated"]