from decimal import Decimal, ROUND_HALF_UP

class CommissionService:
    COMMISSION_RATE = Decimal("0.10")

    @staticmethod
    def calculate(final_price):

        try:
            final_price = Decimal(str(final_price))
        except Exception:
            raise ValueError("Invalid final_price")

        if final_price < 0:
            raise ValueError("final_price cannot be negative")

        commission = (final_price * CommissionService.COMMISSION_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        driver_earning = (final_price - commission).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return commission, driver_earning