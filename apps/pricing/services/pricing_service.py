from decimal import Decimal, ROUND_HALF_UP
from apps.pricing.services.google_maps_service import GoogleMapsService

class PriceCalculator:

    BASE_FEE = Decimal("50")
    WEIGHT_RATE = Decimal("2")
    MIN_PRICE = Decimal("100")

    SURGE_MULTIPLIER = Decimal("1.0")
    WAITING_FEE_PER_MIN = Decimal("2")
    HEAVY_WEIGHT_THRESHOLD = 500
    HEAVY_SURCHARGE = Decimal("100")


    @staticmethod
    def get_distance(shipment):
        if shipment.road_distance_km:
            return Decimal(str(shipment.road_distance_km))

        try:
            distance_km, duration_min = GoogleMapsService.get_distance_and_duration(
                (shipment.pickup_location.y, shipment.pickup_location.x),
                (shipment.dropoff_location.y, shipment.dropoff_location.x),
            )

            shipment.road_distance_km = distance_km
            shipment.estimated_duration_min = duration_min
            shipment.save(update_fields=["road_distance_km", "estimated_duration_min"])

            return Decimal(str(distance_km))

        except Exception:
            # Fallback → Haversine
            from math import radians, sin, cos, sqrt, atan2

            lat1 = shipment.pickup_location.y
            lon1 = shipment.pickup_location.x
            lat2 = shipment.dropoff_location.y
            lon2 = shipment.dropoff_location.x

            R = 6371
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)

            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            distance_km = 2 * R * atan2(sqrt(a), sqrt(1 - a))

            return Decimal(str(distance_km))

    @staticmethod
    def get_rate(distance_km):
        if distance_km < 5:
            return Decimal("8")
        elif distance_km < 20:
            return Decimal("10")
        return Decimal("15")

    @staticmethod
    def _base_price(shipment):
        distance_km = PriceCalculator.get_distance(shipment)
        rate = PriceCalculator.get_rate(distance_km)

        distance_cost = distance_km * rate
        weight_cost = Decimal(str(shipment.weight)) * PriceCalculator.WEIGHT_RATE

        total = PriceCalculator.BASE_FEE + distance_cost + weight_cost

        return total

    @staticmethod
    def calculate_estimated_price(shipment):
        total = PriceCalculator._base_price(shipment)

        # No surge / no waiting / no penalties here
        total = max(total, PriceCalculator.MIN_PRICE)

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_final_price(shipment):
        total = PriceCalculator._base_price(shipment)

        # Heavy cargo
        if shipment.weight > PriceCalculator.HEAVY_WEIGHT_THRESHOLD:
            total += PriceCalculator.HEAVY_SURCHARGE

        # Waiting time
        waiting_minutes = getattr(shipment, "waiting_minutes", 0)
        if waiting_minutes:
            total += Decimal(str(waiting_minutes)) * PriceCalculator.WAITING_FEE_PER_MIN

        # Surge pricing
        total *= PriceCalculator.SURGE_MULTIPLIER

        total = max(total, PriceCalculator.MIN_PRICE)

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)