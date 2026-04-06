from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.pricing.services.pricing_service import PriceCalculator
from apps.shipments.models import ShipmentStatusHistory

from ..models import Assignment

class AssignmentService:
    VALID_TRANSITIONS = {
        "assigned": ["driver_arriving", "cancelled"],
        "driver_arriving": ["in_transit", "cancelled"],
        "in_transit": ["delivered", "cancelled"],
        "delivered": ["completed"],
        "completed": [],
        "cancelled": []
    }

    @staticmethod
    def assign_driver(shipment, driver, vehicle=None):

        if vehicle is None:
            vehicle = driver.vehicles.first()

        assignment = Assignment.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=vehicle,
            status="assigned"
        )

        shipment.status = "assigned"
        shipment.assigned_at = timezone.now()
        shipment.save()

        driver.is_available = False
        driver.save()

        return assignment

    @staticmethod
    def change_status(assignment, new_status, user):
        current_status = assignment.status
        allowed_next = AssignmentService.VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next:
            raise ValidationError(
                f"Invalid status transition from '{current_status}' to '{new_status}'"
            )

        assignment.status = new_status
        assignment.save()

        shipment = assignment.shipment
        shipment.status = new_status

        if new_status == "driver_arriving":
            shipment.assigned_at = shipment.assigned_at or timezone.now()

        if new_status == "in_transit":
            assignment.picked_up_at = timezone.now()
            assignment.save(update_fields=["picked_up_at", "updated_at"])
            shipment.picked_up_at = assignment.picked_up_at

        if new_status == "delivered":
            assignment.delivered_at = timezone.now()
            assignment.save(update_fields=["delivered_at", "updated_at"])
            shipment.delivered_at = assignment.delivered_at

        if new_status == "completed":
            shipment.final_price = PriceCalculator.calculate_final_price(shipment)
            shipment.delivered_at = shipment.delivered_at or timezone.now()

        shipment.save()
        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status=shipment.status,
            changed_by=user,
            notes=f"Assignment status changed from {current_status} to {new_status}",
        )

        return assignment
