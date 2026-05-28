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

class AssignmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[choice[0] for choice in Assignment.STATUS_CHOICES])
    proof_of_delivery = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        status = attrs.get("status")
        proof = attrs.get("proof_of_delivery")

        if status == "delivered" and not proof:
            raise serializers.ValidationError(
                {"proof_of_delivery": "Proof of delivery is required when marking a shipment as delivered."}
            )

        if status != "delivered" and proof:
            raise serializers.ValidationError(
                {"proof_of_delivery": "Proof of delivery can only be uploaded when the status is delivered."}
            )

        return attrs
