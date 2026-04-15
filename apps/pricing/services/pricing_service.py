from decimal import Decimal, ROUND_HALF_UP
from ..services.osrm_service import OSRMService
from apps.pricing.services.google_maps_service import GoogleMapsService

class PriceCalculator:

    BASE_FEE = Decimal("50")
    PRICE_PER_KM = Decimal("10")
    WEIGHT_RATE = Decimal("2")

    @staticmethod
    def calculate_estimated_price(shipment):
        try:
            distance_km, duration_min = GoogleMapsService.get_distance_and_duration(
                (shipment.pickup_location.y, shipment.pickup_location.x),
                (shipment.dropoff_location.y, shipment.dropoff_location.x),
            )

            # cache for later use
            shipment.road_distance_km = distance_km
            shipment.estimated_duration_min = duration_min
            shipment.save(update_fields=["road_distance_km", "estimated_duration_min"])

        except Exception:
            # fallback (Haversine)
            from math import radians, sin, cos, sqrt, atan2

            def haversine(lat1, lon1, lat2, lon2):
                R = 6371
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                return 2 * R * atan2(sqrt(a), sqrt(1 - a))

            distance_km = haversine(
                shipment.pickup_location.y,
                shipment.pickup_location.x,
                shipment.dropoff_location.y,
                shipment.dropoff_location.x,
            )

        distance_km = Decimal(str(distance_km))

        # Pricing tiers
        if distance_km < 5:
            rate = Decimal("8")
        elif distance_km < 20:
            rate = Decimal("10")
        else:
            rate = Decimal("15")

        distance_cost = distance_km * rate
        weight_cost = Decimal(str(shipment.weight)) * PriceCalculator.WEIGHT_RATE

        total = PriceCalculator.BASE_FEE + distance_cost + weight_cost

        total = max(total, Decimal("100"))

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_final_price(shipment):

        # Use cached distance if available
        if shipment.road_distance_km:
            road_distance_km = shipment.road_distance_km
        else:
            try:
                road_distance_km = OSRMService.get_road_distance(
                    shipment.pickup_location,
                    shipment.dropoff_location
                )

                # Save
                shipment.road_distance_km = road_distance_km
                shipment.save(update_fields=["road_distance_km"])

            except Exception:
                road_distance_km = shipment.pickup_location.distance(
                    shipment.dropoff_location
                ) / 1000

        distance_km = Decimal(str(road_distance_km))

        # Pricing tiers
        if distance_km < 5:
            rate = Decimal("8")
        elif distance_km < 20:
            rate = Decimal("10")
        else:
            rate = Decimal("15")

        distance_cost = distance_km * rate
        weight_cost = Decimal(str(shipment.weight)) * PriceCalculator.WEIGHT_RATE

        total = PriceCalculator.BASE_FEE + distance_cost + weight_cost

        # Extra fee
        if shipment.weight > 500:
            total += Decimal("100")

        # Minimum fare
        total = max(total, Decimal("100"))

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
