from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils import timezone
from datetime import timedelta
from apps.tracking.models import DriverLocation
from apps.matching.models import DriverOffer
from apps.shipments.models import ShipmentStatusHistory


class MatchingService:
    SEARCH_RADIUS_KM = 10
    MAX_CANDIDATES = 5
    # OFFER_TIMEOUT_SECONDS = 30
    OFFER_TIMEOUT_SECONDS = 600


    @staticmethod
    def find_nearest_drivers(shipment):
        pickup_point = shipment.pickup_location

        return (
            DriverLocation.objects
            .filter(
                driver__is_available=True,
                is_online=True
            )
            .annotate(distance=Distance("location", pickup_point))
            .filter(
                location__distance_lte=(
                    pickup_point,
                    D(km=MatchingService.SEARCH_RADIUS_KM)
                )
            )
            .order_by("distance")[:MatchingService.MAX_CANDIDATES]
        )

    @staticmethod
    def match_driver(shipment):

        if shipment.status != "matching":
            return None

        drivers = MatchingService.find_nearest_drivers(shipment)

        if not drivers:
            print("No drivers found")
            
            shipment.status = "no_driver"
            shipment.save()
            ShipmentStatusHistory.objects.create(
                shipment=shipment,
                status=shipment.status,
                notes="No drivers available in search radius",
            )
            return None

        for d in drivers:
            driver = d.driver

            if DriverOffer.objects.filter(
                    shipment=shipment,
                    driver=driver
            ).exists():
                continue

            offer = MatchingService.create_offer(shipment, driver)

            print(f"Offer sent to {driver.user.email}")
            return offer

        return None

    @staticmethod
    def match_next_driver(shipment):

        tried_driver_ids = DriverOffer.objects.filter(
            shipment=shipment
        ).values_list("driver_id", flat=True)

        pickup_point = shipment.pickup_location

        drivers = (
            DriverLocation.objects
            .exclude(driver_id__in=tried_driver_ids)
            .filter(driver__is_available=True, is_online=True)
            .annotate(distance=Distance("location", pickup_point))
            .filter(
                location__distance_lte=(
                    pickup_point,
                    D(km=MatchingService.SEARCH_RADIUS_KM)
                )
            )
            .order_by("distance")[:MatchingService.MAX_CANDIDATES]
        )

        if not drivers:
            print("No more drivers available")
            shipment.status = "no_driver"
            shipment.save()
            ShipmentStatusHistory.objects.create(
                shipment=shipment,
                status=shipment.status,
                notes="No more drivers available after offer retries",
            )
            return None

        for d in drivers:
            driver = d.driver

            offer = MatchingService.create_offer(shipment, driver)

            print(f"Next offer sent to {driver.user.email}")
            return offer

        return None

    @staticmethod
    def create_offer(shipment, driver):
        return DriverOffer.objects.create(
            shipment=shipment,
            driver=driver,
            status="pending",
            expires_at=timezone.now() + timedelta(
                seconds=MatchingService.OFFER_TIMEOUT_SECONDS
            )
        )