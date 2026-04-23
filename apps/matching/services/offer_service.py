from django.utils import timezone
from django.db import transaction
from apps.matching.models import DriverOffer
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
            ).values_list("id", flat=True)[:20]  # batch limit
        )

        print(f"Found {len(expired_ids)} expired offers")

        for offer_id in expired_ids:
            try:
                with transaction.atomic():

                    offer = (
                        DriverOffer.objects
                        .select_for_update(skip_locked=True)
                        .select_related("shipment", "driver", "driver__user")
                        .get(id=offer_id)
                    )

                    # Safety check
                    if offer.status != "pending":
                        continue

                    shipment = offer.shipment
                    driver = offer.driver

                    # expire
                    offer.status = "expired"
                    offer.save(update_fields=["status"])

                    print(f"Offer expired for {driver.user.email}")

                    # Notify DRIVER
                    notify_user(
                        user=driver.user,
                        title="Offer Expired",
                        message="You did not respond in time. The request has been reassigned.",
                        data={
                            "type": "offer_expired",
                            "shipment_id": shipment.id,
                            "offer_id": offer.id
                        }
                    )

                    # Only continue if shipment still needs matching
                    if shipment.status != "matching":
                        continue

                    # Notify CUSTOMER
                    notify_user(
                        user=shipment.customer,
                        title="Finding Another Driver",
                        message="Previous driver didn’t respond. Searching for another driver...",
                        data={
                            "type": "driver_reassign",
                            "shipment_id": shipment.id
                        }
                    )

                    # Async matching
                    start_driver_matching.delay(shipment.id)

            except DriverOffer.DoesNotExist:
                continue