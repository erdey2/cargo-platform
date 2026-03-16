from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from decimal import Decimal


class PriceCalculator:

    BASE_FEE = Decimal("50")
    PRICE_PER_KM = Decimal("10")
    WEIGHT_RATE = Decimal("2")

    @staticmethod
    def calculate_estimated_price(shipment):

        pickup = shipment.pickup_location
        dropoff = shipment.dropoff_location

        distance_km = pickup.distance(dropoff) * 100  # approximate km

        distance_cost = Decimal(distance_km) * PriceCalculator.PRICE_PER_KM
        weight_cost = Decimal(shipment.weight) * PriceCalculator.WEIGHT_RATE

        total = (
            PriceCalculator.BASE_FEE +
            distance_cost +
            weight_cost
        )

        return round(total, 2)

    @staticmethod
    def calculate_final_price(shipment):
        estimated = shipment.estimated_price

        # Example adjustments
        extra_fee = Decimal("0")

        if shipment.weight > 500:
            extra_fee += Decimal("100")

        return estimated + extra_fee