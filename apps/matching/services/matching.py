from django.db import transaction
from django.db.models import Exists, OuterRef
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils import timezone
from datetime import timedelta
from apps.tracking.models import DriverLocation
from apps.matching.models import DriverOffer
from apps.shipments.models import ShipmentStatusHistory
from apps.vehicles.models import Vehicle
from apps.notifications.services import notify_user


class MatchingService:
    SEARCH_RADIUS_KM = 10
    MAX_CANDIDATES = 5
    OFFER_TIMEOUT_SECONDS = 600

    @staticmethod
    def get_valid_vehicle_subquery(shipment):
        return Vehicle.objects.filter(
            driver=OuterRef("driver"),
            verification_status=True,
            capacity_weight__gte=shipment.weight,
            capacity_volume__gte=shipment.volume,
        )

    # Core driver search
    @staticmethod
    def find_nearest_drivers(shipment):
        pickup_point = shipment.pickup_location
        valid_vehicle = MatchingService.get_valid_vehicle_subquery(shipment)

        return (
            DriverLocation.objects
            .filter(
                driver__is_available=True,
                driver__verification_status="verified",
                is_online=True
            )
            .annotate(
                has_valid_vehicle=Exists(valid_vehicle),
                distance=Distance("location", pickup_point)
            )
            .filter(
                has_valid_vehicle=True,
                location__distance_lte=(pickup_point, D(km=MatchingService.SEARCH_RADIUS_KM))
            )
            .select_related("driver", "driver__user")
            .order_by("distance", "-driver__rating")[:MatchingService.MAX_CANDIDATES]
        )

    # Select BEST vehicle
    @staticmethod
    def get_best_vehicle(driver, shipment):
        return (
            Vehicle.objects
            .filter(
                driver=driver,
                verification_status=True,
                capacity_weight__gte=shipment.weight,
                capacity_volume__gte=shipment.volume,
            )
            .order_by("capacity_weight", "capacity_volume")  # smallest sufficient
            .first()
        )

    # MAIN MATCHING (with transaction safety)
    @staticmethod
    @transaction.atomic
    def match_driver(shipment):

        if shipment.status != "matching":
            return None

        drivers = MatchingService.find_nearest_drivers(shipment)

        if not drivers:
            shipment.status = "no_driver"
            shipment.save(update_fields=["status"])

            ShipmentStatusHistory.objects.create(
                shipment=shipment,
                status=shipment.status,
                notes="No drivers available in search radius",
            )

            # Notify customer
            notify_user(
                user=shipment.customer,
                title="No Driver Available",
                message="We couldn’t find a driver nearby. Please try again later.",
                data={
                    "type": "no_driver",
                    "shipment_id": shipment.id
                }
            )

            return None

        for d in drivers:
            driver = d.driver

            # avoid duplicate offers
            if DriverOffer.objects.filter(
                shipment=shipment,
                driver=driver
            ).exists():
                continue

            # select vehicle
            vehicle = MatchingService.get_best_vehicle(driver, shipment)
            if not vehicle:
                continue

            return MatchingService.create_offer(shipment, driver, vehicle)

        return None

    # MATCH NEXT DRIVER
    @staticmethod
    @transaction.atomic
    def match_next_driver(shipment):

        tried_driver_ids = DriverOffer.objects.filter(
            shipment=shipment
        ).values_list("driver_id", flat=True)

        pickup_point = shipment.pickup_location
        valid_vehicle = MatchingService.get_valid_vehicle_subquery(shipment)

        drivers = (
            DriverLocation.objects
            .exclude(driver_id__in=tried_driver_ids)
            .filter(
                driver__is_available=True,
                driver__verification_status="verified",
                is_online=True
            )
            .annotate(
                has_valid_vehicle=Exists(valid_vehicle),
                distance=Distance("location", pickup_point)
            )
            .filter(
                has_valid_vehicle=True,
                location__distance_lte=(pickup_point, D(km=MatchingService.SEARCH_RADIUS_KM))
            )
            .select_related("driver", "driver__user")
            .order_by("distance", "-driver__rating")[:MatchingService.MAX_CANDIDATES] # order by distance then rating
        )

        if not drivers:
            shipment.status = "no_driver"
            shipment.save(update_fields=["status"])

            ShipmentStatusHistory.objects.create(
                shipment=shipment,
                status=shipment.status,
                notes="No more drivers available after retries",
            )

            # Notify customer
            notify_user(
                user=shipment.customer,
                title="No More Drivers",
                message="No drivers available after multiple attempts.",
                data={
                    "type": "no_driver_retry",
                    "shipment_id": shipment.id
                }
            )
            return None

        for d in drivers:
            driver = d.driver

            vehicle = MatchingService.get_best_vehicle(driver, shipment)
            if not vehicle:
                continue

            return MatchingService.create_offer(shipment, driver, vehicle)

        return None

    # CREATE OFFER
    @staticmethod
    def create_offer(shipment, driver, vehicle):
        offer = DriverOffer.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=vehicle,
            status="pending",
            expires_at=timezone.now() + timedelta(
                seconds=MatchingService.OFFER_TIMEOUT_SECONDS
            )
        )
        # Notify CUSTOMER
        notify_user(
            user=shipment.customer,
            title="Driver Found for Your Shipment",
            message="A driver has been found and notified.",
            data={
                "type": "driver_found",
                "shipment_id": shipment.id,
                "driver_id": driver.id,
                "offer_id": offer.id
            }
        )

        # Notify DRIVER
        notify_user(
            user=driver.user,
            title="New Delivery Request",
            message="You have a new shipment request.",
            data={
                "type": "new_offer",
                "shipment_id": shipment.id,
                "offer_id": offer.id
            }
        )

        return offer


