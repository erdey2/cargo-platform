from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from apps.tracking.models import DriverLocation
from apps.assignment.services.assignment import AssignmentService
import time


class MatchingService:
    SEARCH_RADIUS_KM = 10
    MAX_CANDIDATES = 5

    @staticmethod
    def match_driver(shipment):

        if shipment.status != "matching":
            return None

        pickup_point = shipment.pickup_location

        drivers = (
            DriverLocation.objects
            .filter(
                driver__is_available=True,
                driver__vehicles__capacity_weight__gte=shipment.weight,
                driver__vehicles__capacity_volume__gte=shipment.volume
            )
            .annotate(distance=Distance("location", pickup_point))
            .filter(location__distance_lte=(pickup_point, D(km=MatchingService.SEARCH_RADIUS_KM)))
            .order_by("distance")
            .distinct()[:MatchingService.MAX_CANDIDATES]
        )

        for driver_location in drivers:
            driver = driver_location.driver
            accepted = NotificationService.notify_driver(driver, shipment)
            if accepted:
                AssignmentService.assign_driver(shipment, driver)
                return driver
            time.sleep(10)

        return None