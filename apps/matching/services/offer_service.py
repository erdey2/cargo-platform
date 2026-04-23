from django.utils import timezone
from apps.matching.models import DriverOffer
from apps.matching.services.matching import MatchingService
from apps.notifications.services import notify_user

class OfferService:

    @staticmethod
    def expire_and_reassign():
        from apps.matching.tasks import start_driver_matching
        now = timezone.now()

        expired_offers = (
            DriverOffer.objects
            .select_for_update(skip_locked=True)
            .select_related("shipment", "driver", "driver__user")
            .filter(
                status="pending",
                expires_at__lte=now
            )
        )
        print(f"Found {expired_offers.count()} expired offers")

        for offer in expired_offers:

            # Skip if already processed (safety)
            if offer.status != "pending":
                continue

            shipment = offer.shipment
            driver = offer.driver

            # Mark expired
            offer.status = "expired"
            offer.save(update_fields=["status"])

            print(f"Offer expired for {driver.user.email}")

            # Notify DRIVER (offer expired)
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

            # Notify CUSTOMER (reassigning)
            notify_user(
                user=shipment.customer,
                title="Finding Another Driver",
                message="Previous driver didn’t respond. Searching for another driver...",
                data={
                    "type": "driver_reassign",
                    "shipment_id": shipment.id
                }
            )

            # Assign next driver

            start_driver_matching.delay(shipment.id)
            # MatchingService.match_next_driver(shipment)
            print(f"Checking expired offers at {now}")
            print(f"Found {expired_offers.count()} expired offers")

