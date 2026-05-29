from django.utils import timezone
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from ..models import Assignment
from apps.shipments.models import ShipmentStatusHistory
from apps.pricing.services.pricing_service import PriceCalculator
from apps.notifications.services import notify_user

from apps.wallet.services.commision_service import CommissionService
from apps.wallet.services.wallet_service import WalletService


class AssignmentService:

    VALID_TRANSITIONS = {
        "assigned": ["driver_arriving", "cancelled"],
        "driver_arriving": ["in_transit", "cancelled"],
        "in_transit": ["delivered", "cancelled"],
        "delivered": ["completed"],
        "completed": [],
        "cancelled": [],
    }

    # ASSIGN DRIVER
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

        shipment.driver = driver
        shipment.status = "assigned"
        shipment.assigned_at = timezone.now()
        shipment.save(update_fields=["driver", "status", "assigned_at", "updated_at"])

        driver.is_available = False
        driver.save(update_fields=["is_available"])

        transaction.on_commit(lambda: notify_user(
            user=shipment.customer,
            title="Driver Assigned",
            message="A driver has been assigned to your shipment.",
            data={
                "type": "driver_assigned",
                "shipment_id": shipment.id,
                "driver_id": driver.id
            }
        ))

        return assignment

    # CHANGE STATUS
    @staticmethod
    @transaction.atomic
    def change_status(assignment, new_status, user, proof_of_delivery=None):
        assignment = Assignment.objects.select_for_update().get(pk=assignment.pk)
        shipment = assignment.shipment

        if not shipment.driver:
            shipment.driver = assignment.driver
            shipment.save(update_fields=["driver"])

        current_status = assignment.status
        allowed_next = AssignmentService.VALID_TRANSITIONS.get(current_status, [])

        if new_status not in allowed_next:
            raise ValidationError({
                "status": f"Cannot change from '{current_status}' to '{new_status}'"
            })

        if new_status == "cancelled" and not user.is_staff:
            raise ValidationError("Only admin can cancel assignments")

        driver = assignment.driver
        customer = shipment.customer
        now = timezone.now()

        assignment.status = new_status
        shipment.status = new_status

        update_fields_assignment = ["status", "updated_at"]
        update_fields_shipment = ["status", "updated_at"]

        # STATUS HANDLING
        if new_status == "in_transit":
            assignment.picked_up_at = now
            shipment.picked_up_at = now
            update_fields_assignment.append("picked_up_at")
            update_fields_shipment.append("picked_up_at")

        elif new_status == "delivered":
            if not proof_of_delivery:
                raise ValidationError("Proof of delivery is required when marking shipment as delivered")

            assignment.delivered_at = now
            shipment.delivered_at = now
            shipment.proof_of_delivery = proof_of_delivery
            update_fields_assignment.append("delivered_at")
            update_fields_shipment.extend(["delivered_at", "proof_of_delivery"])

        elif new_status == "completed":

            if shipment.is_paid:
                raise ValidationError("Shipment already paid")

            final_price = PriceCalculator.calculate_final_price(shipment)

            shipment.final_price = final_price
            update_fields_shipment.append("final_price")

            if not shipment.delivered_at:
                shipment.delivered_at = now
                update_fields_shipment.append("delivered_at")

            commission, _ = CommissionService.calculate(final_price)

            WalletService.credit_driver(
                driver,
                final_price,
                f"shipment_{shipment.id}",
                description=f"Shipment {shipment.id} earning",
                platform_fee=commission,
            )  # type: ignore[call-arg]

            shipment.is_paid = True
            update_fields_shipment.append("is_paid")

            driver.total_trips = F("total_trips") + 1
            driver.is_available = not driver.shipments.filter(
                status__in=["assigned", "in_transit"]
            ).exists()

            driver.save(update_fields=["total_trips", "is_available"])

        elif new_status == "cancelled":
            driver.is_available = True
            driver.save(update_fields=["is_available"])

        # SAVE
        assignment.save(update_fields=update_fields_assignment)
        shipment.save(update_fields=update_fields_shipment)

        # HISTORY
        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status=new_status,
            changed_by=user,
            notes=f"Assignment status changed from {current_status} to {new_status}",
        )

        # NOTIFICATIONS
        def send_notifications():
            if new_status == "driver_arriving":
                notify_user(
                    user=customer,
                    title="Driver is Coming",
                    message="Your driver is on the way.",
                    data={"type": "driver_arriving", "shipment_id": shipment.id}
                )

            elif new_status == "in_transit":
                notify_user(
                    user=customer,
                    title="Shipment Picked Up",
                    message="Your shipment is in transit.",
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
                    message="Shipment completed successfully.",
                    data={
                        "type": "completed",
                        "shipment_id": shipment.id,
                        "final_price": str(shipment.final_price)
                    }
                )

            elif new_status == "cancelled":
                notify_user(
                    user=customer,
                    title="Shipment Cancelled",
                    message="Your shipment was cancelled.",
                    data={"type": "cancelled", "shipment_id": shipment.id}
                )

                notify_user(
                    user=driver.user,
                    title="Assignment Cancelled",
                    message="Shipment assignment cancelled.",
                    data={"type": "cancelled", "shipment_id": shipment.id}
                )

        transaction.on_commit(send_notifications)

        # REALTIME UPDATE
        transaction.on_commit(
            lambda: AssignmentService.broadcast_status_update(
                assignment, shipment, new_status
            )  # type: ignore[arg-type]
        )

        return assignment

    # WEBSOCKET
    @staticmethod
    def broadcast_status_update(assignment, shipment, status):

        proof = getattr(shipment, "proof_of_delivery", None)
        proof_url = getattr(proof, "url", None) if proof else None

        payload = {
            "event": "assignment.status",
            "data": {
                "shipment_id": shipment.id,
                "assignment_id": assignment.id,
                "status": status,
                "changed_at": shipment.updated_at.isoformat(),
                "final_price": str(shipment.final_price) if shipment.final_price else None,
                "proof_of_delivery": proof_url,
            },
        }

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        for role in ("customer", "driver", "admin"):
            async_to_sync(channel_layer.group_send)(
                f"shipment_{shipment.id}_{role}",
                {"type": "assignment_status_event", "payload": payload},
            )