from django.utils import timezone
from apps.matching.models import DriverOffer
from apps.matching.services.matching import MatchingService


class OfferService:

    @staticmethod
    def expire_and_reassign():
        now = timezone.now()

        expired_offers = DriverOffer.objects.select_related(
            "shipment", "driver"
        ).filter(
            status="pending",
            expires_at__lte=now
        )

        for offer in expired_offers:

            # Skip if already processed (safety)
            if offer.status != "pending":
                continue

            # Mark expired
            offer.status = "expired"
            offer.save(update_fields=["status"])

            shipment = offer.shipment

            # Only continue if shipment still needs matching
            if shipment.status != "matching":
                continue

            print(f"Offer expired for {offer.driver.user.email}")

            # Assign next driver
            MatchingService.match_next_driver(shipment)