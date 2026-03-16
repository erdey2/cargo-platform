from rest_framework import serializers
from ..models import DriverLocation

class DriverLocationSerializer(serializers.ModelSerializer):

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
        read_only_fields = ["driver", "last_updated"]