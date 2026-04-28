from decimal import Decimal, ROUND_HALF_UP

class CommissionService:
    COMMISSION_RATE = Decimal("0.10")

    @staticmethod
    def calculate(final_price):
        if final_price is None:
            raise ValueError("final_price cannot be None")

        final_price = Decimal(final_price)

        commission = (final_price * CommissionService.COMMISSION_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        driver_earning = (final_price - commission).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return commission, driver_earning