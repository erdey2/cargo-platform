from rest_framework import serializers
from ..models import VehicleType, Vehicle, VehicleDocument

class VehicleTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = VehicleType
        fields = "__all__"

class VehicleSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id",
            "plate_number",
            "vehicle_type",
            "capacity",
        ]

class VehicleSerializer(serializers.ModelSerializer):

    driver = serializers.ReadOnlyField(source="driver.id")

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "driver",
            "vehicle_type",
            "plate_number",
            "capacity_weight",
            "capacity_volume",
            "verification_status",
        ]
        read_only_fields = ["verification_status"]

class VehicleDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = VehicleDocument
        fields = [
            "id",
            "vehicle",
            "document_name",
            "file",
            "is_verified",
            "created_at",
        ]
        read_only_fields = ["is_verified"]