from decimal import Decimal, ROUND_HALF_UP
from ..services.osrm_service import OSRMService

class PriceCalculator:

    BASE_FEE = Decimal("50")
    PRICE_PER_KM = Decimal("10")
    WEIGHT_RATE = Decimal("2")

    @staticmethod
    def calculate_estimated_price(shipment):
        distance_m = shipment.pickup_location.distance(shipment.dropoff_location)

        # Convert to Decimal safely
        distance_km = Decimal(str(distance_m)) / Decimal("1000")

        # Distance-based pricing tiers
        if distance_km < 5:
            rate = Decimal("8")
        elif distance_km < 20:
            rate = Decimal("10")
        else:
            rate = Decimal("15")

        distance_cost = distance_km * rate

        # Weight cost
        weight_cost = Decimal(str(shipment.weight)) * PriceCalculator.WEIGHT_RATE

        total = PriceCalculator.BASE_FEE + distance_cost + weight_cost

        # Minimum fare
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
