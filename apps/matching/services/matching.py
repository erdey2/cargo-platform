from django.db import transaction, IntegrityError
from django.db.models import Exists, OuterRef
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils import timezone
from datetime import timedelta

from apps.tracking.models import DriverLocation
from apps.matching.models import DriverOffer
from apps.shipments.models import Shipment, ShipmentStatusHistory
from apps.vehicles.models import Vehicle
from apps.notifications.services import notify_user

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class MatchingService:
    SEARCH_RADIUS_KM = 10
    MAX_CANDIDATES = 5
    OFFER_TIMEOUT_SECONDS = 60

    @staticmethod
    def get_valid_vehicle_subquery(shipment):
        return Vehicle.objects.filter(
            driver=OuterRef("driver"),
            verification_status=True,
            capacity_weight__gte=shipment.weight,
            capacity_volume__gte=shipment.volume,
        )

    @staticmethod
    def find_nearest_drivers(shipment, exclude_driver_ids=None):
        pickup_point = shipment.pickup_location
        valid_vehicle = MatchingService.get_valid_vehicle_subquery(shipment)

        queryset = DriverLocation.objects.filter(
            driver__is_available=True,
            driver__verification_status="verified",
            is_online=True,
        )

        if exclude_driver_ids:
            queryset = queryset.exclude(driver_id__in=exclude_driver_ids)

        return (
            queryset
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

    @staticmethod
    def mark_no_driver(shipment):
        shipment.status = "no_driver"
        shipment.save(update_fields=["status"])

        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status="no_driver",
            notes="No drivers available"
        )

        notify_user(
            user=shipment.customer,
            title="No Driver Available",
            message="Try again later.",
            data={"type": "no_driver", "shipment_id": shipment.id}
        )

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
            .order_by("capacity_weight", "capacity_volume")
            .first()
        )

    @staticmethod
    @transaction.atomic
    def match_driver(shipment):

        shipment = Shipment.objects.select_for_update().get(id=shipment.id)

        if shipment.status != "matching":
            return None

        if DriverOffer.objects.filter(shipment=shipment, status="pending").exists():
            return None

        drivers = MatchingService.find_nearest_drivers(shipment)

        if not drivers:
            MatchingService.mark_no_driver(shipment)
            return None

        for d in drivers:
            driver = d.driver

            # Avoid duplicate offers
            if DriverOffer.objects.filter(
                shipment=shipment,
                driver=driver
            ).exists():
                continue

            vehicle = MatchingService.get_best_vehicle(driver, shipment)
            if not vehicle:
                continue

            return MatchingService.create_offer(shipment, driver, vehicle, d)

        return None

    @staticmethod
    @transaction.atomic
    def match_next_driver(shipment):
        shipment = Shipment.objects.select_for_update().get(id=shipment.id)

        if shipment.status != "matching":
            return None

        if DriverOffer.objects.filter(shipment=shipment, status="pending").exists():
            return None

        offered_driver_ids = DriverOffer.objects.filter(
            shipment=shipment
        ).values_list("driver_id", flat=True)
        drivers = MatchingService.find_nearest_drivers(
            shipment,
            exclude_driver_ids=offered_driver_ids,
        )

        if not drivers:
            MatchingService.mark_no_driver(shipment)
            return None

        for d in drivers:
            vehicle = MatchingService.get_best_vehicle(d.driver, shipment)
            if not vehicle:
                continue

            return MatchingService.create_offer(shipment, d.driver, vehicle, d)

        MatchingService.mark_no_driver(shipment)
        return None

    @staticmethod
    def create_offer(shipment, driver, vehicle, driver_location_obj):
        try:
            offer = DriverOffer.objects.create(
                shipment=shipment,
                driver=driver,
                vehicle=vehicle,
                status="pending",
                expires_at=timezone.now() + timedelta(
                    seconds=MatchingService.OFFER_TIMEOUT_SECONDS
                )
            )
        except IntegrityError:
            return DriverOffer.objects.get(shipment=shipment, driver=driver)

        lat = driver_location_obj.location.y if driver_location_obj.location else None
        lng = driver_location_obj.location.x if driver_location_obj.location else None

        # WebSocket notify
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"shipment_{shipment.id}_customer",
            {
                "type": "driver_found_event",
                "payload": {
                    "event": "driver_found",
                    "data": {
                        "driver": {
                            "id": driver.id,
                            "name": driver.user.get_full_name(),
                            "rating": getattr(driver, "rating", None),
                        },
                        "vehicle": {
                            "id": vehicle.id,
                            "type": getattr(vehicle, "vehicle_type", None),
                        },
                        "location": {
                            "lat": lat,
                            "lng": lng
                        },
                        "shipment_id": shipment.id,
                        "status": "matched"
                    }
                }
            }
        )

        # Notifications
        notify_user(
            user=shipment.customer,
            title="Driver Found",
            message="Driver is reviewing your request.",
            data={
                "type": "driver_found",
                "shipment_id": shipment.id,
                "driver_id": driver.id,
                "offer_id": offer.id
            }
        )

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