from django.utils import timezone
from django.db import transaction
from apps.matching.models import DriverOffer
from apps.shipments.models import Shipment
from apps.notifications.services import notify_user


class OfferService:

    @staticmethod
    def expire_and_reassign():
        from apps.matching.tasks import start_driver_matching

        now = timezone.now()

        expired_ids = list(
            DriverOffer.objects.filter(
                status="pending",
                expires_at__lte=now
            ).values_list("id", flat=True)[:20]
        )

        for offer_id in expired_ids:
            try:
                with transaction.atomic():

                    offer = (
                        DriverOffer.objects
                        .select_for_update(skip_locked=True)
                        .select_related("driver", "driver__user")
                        .get(id=offer_id)
                    )

                    if offer.status != "pending":
                        continue

                    shipment = Shipment.objects.select_for_update().get(
                        id=offer.shipment_id
                    )

                    if shipment.driver is not None:
                        continue

                    if shipment.status != "matching":
                        continue

                    # SAFE TO EXPIRE
                    offer.status = "expired"
                    offer.save(update_fields=["status"])

                    notify_user(
                        user=offer.driver.user,
                        title="Offer Expired",
                        message="Request reassigned.",
                        data={"type": "offer_expired", "shipment_id": shipment.id}
                    )

                    notify_user(
                        user=shipment.customer,
                        title="Finding Another Driver",
                        message="Searching for another driver...",
                        data={"type": "driver_reassign", "shipment_id": shipment.id}
                    )

                    start_driver_matching.delay(shipment.id)

            except DriverOffer.DoesNotExist:
                continue