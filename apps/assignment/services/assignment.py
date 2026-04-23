from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from ..models import Assignment
from apps.shipments.models import ShipmentStatusHistory
from apps.pricing.services.pricing_service import PriceCalculator
from apps.notifications.services import notify_user

class AssignmentService:

    VALID_TRANSITIONS = {
        "assigned": ["driver_arriving", "cancelled"],
        "driver_arriving": ["in_transit", "cancelled"],
        "in_transit": ["delivered", "cancelled"],
        "delivered": ["completed"],
        "completed": [],
        "cancelled": [],
    }

    @staticmethod
    @transaction.atomic
    def assign_driver(shipment, driver, vehicle=None):

        if vehicle is None:
            vehicle = driver.vehicles.first()

        if not vehicle:
            raise ValidationError("Driver has no assigned vehicle")

        assignment = Assignment.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=vehicle,
            status="assigned"
        )

        shipment.status = "assigned"
        shipment.assigned_at = timezone.now()
        shipment.save(update_fields=["status", "assigned_at", "updated_at"])

        driver.is_available = False
        driver.save(update_fields=["is_available"])

        # Notify CUSTOMER
        notify_user(
            user=shipment.customer,
            title="Driver Assigned",
            message="A driver has been assigned to your shipment.",
            data={
                "type": "driver_assigned",
                "shipment_id": shipment.id,
                "driver_id": driver.id
            }
        )

        return assignment

    @staticmethod
    @transaction.atomic
    def change_status(assignment, new_status, user):

        current_status = assignment.status
        allowed_next = AssignmentService.VALID_TRANSITIONS.get(current_status, [])

        if new_status not in allowed_next:
            raise ValidationError({
                "status": f"Cannot change from '{current_status}' to '{new_status}'"
            })

        if new_status == "cancelled" and not user.is_staff:
            raise ValidationError("Only admin can cancel assignments")

        shipment = assignment.shipment
        driver = assignment.driver
        customer = shipment.customer

        now = timezone.now()

        assignment.status = new_status
        shipment.status = new_status

        update_fields_assignment = ["status", "updated_at"]
        update_fields_shipment = ["status", "updated_at"]

        # Timestamp handling
        if new_status == "in_transit":
            assignment.picked_up_at = now
            shipment.picked_up_at = now
            update_fields_assignment.append("picked_up_at")
            update_fields_shipment.append("picked_up_at")

        elif new_status == "delivered":
            assignment.delivered_at = now
            shipment.delivered_at = now
            update_fields_assignment.append("delivered_at")
            update_fields_shipment.append("delivered_at")

        elif new_status == "completed":
            shipment.final_price = PriceCalculator.calculate_final_price(shipment)
            update_fields_shipment.append("final_price")

            if not shipment.delivered_at:
                shipment.delivered_at = now
                update_fields_shipment.append("delivered_at")

        # Driver becomes available again
        if new_status in ["completed", "cancelled"]:
            driver.is_available = True
            driver.save(update_fields=["is_available"])

        assignment.save(update_fields=update_fields_assignment)
        shipment.save(update_fields=update_fields_shipment)

        # History logging
        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status=new_status,
            changed_by=user,
            notes=f"Assignment status changed from {current_status} to {new_status}",
        )

        # NOTIFICATIONS

        if new_status == "driver_arriving":
            notify_user(
                user=customer,
                title="Driver is Coming",
                message="Your driver is on the way to pickup location.",
                data={"type": "driver_arriving", "shipment_id": shipment.id}
            )

        elif new_status == "in_transit":
            notify_user(
                user=customer,
                title="Shipment Picked Up",
                message="Your shipment is now in transit.",
                data={"type": "in_transit", "shipment_id": shipment.id}
            )

        elif new_status == "delivered":
            notify_user(
                user=customer,
                title="Shipment Delivered",
                message="Your shipment has been delivered.",
                data={"type": "delivered", "shipment_id": shipment.id}
            )

        elif new_status == "completed":
            notify_user(
                user=customer,
                title="Shipment Completed",
                message="Your shipment has been completed successfully.",
                data={
                    "type": "completed",
                    "shipment_id": shipment.id,
                    "final_price": shipment.final_price
                }
            )

        elif new_status == "cancelled":
            # Notify both sides
            notify_user(
                user=customer,
                title="Shipment Cancelled",
                message="Your shipment has been cancelled.",
                data={"type": "cancelled", "shipment_id": shipment.id}
            )

            notify_user(
                user=driver.user,
                title="Assignment Cancelled",
                message="This shipment assignment has been cancelled.",
                data={"type": "cancelled", "shipment_id": shipment.id}
            )

        # Push shipment status changes to active tracking screens after commit.
        transaction.on_commit(
            lambda: AssignmentService.broadcast_status_update(assignment, shipment, new_status)
        )

        return assignment

    @staticmethod
    def broadcast_status_update(assignment, shipment, status):
        shipment_id = getattr(shipment, "id", None)
        assignment_id = getattr(assignment, "id", None)

        if shipment_id is None:
            return

        payload = {
            "event": "assignment.status",
            "data": {
                "shipment_id": shipment_id,
                "assignment_id": assignment_id,
                "status": status,
                "changed_at": timezone.now().isoformat(),
                "final_price": getattr(shipment, "final_price", None),
            },
        }

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        for role in ("customer", "driver", "admin"):
            async_to_sync(channel_layer.group_send)(
                f"shipment_{shipment_id}_{role}",
                {"type": "assignment_status_event", "payload": payload},
            )
