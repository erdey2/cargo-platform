from rest_framework import serializers
from apps.drivers.models import DriverProfile

class DriverSimpleSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.profile.full_name", read_only=True)

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "email",
            "full_name",
            "rating",
            "total_trips",
            "is_available",
        ]