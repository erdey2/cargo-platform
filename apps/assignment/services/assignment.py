from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.pricing.services.pricing_service import PriceCalculator

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
        assignment.status = new_status
        assignment.save()

        shipment = assignment.shipment

        if new_status == "completed":
            shipment.final_price = PriceCalculator.calculate_final_price(shipment)
            shipment.save()

        return assignment
