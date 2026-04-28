from decimal import Decimal


class CommissionService:
    COMMISSION_RATE = Decimal("0.10")  # 10%

    @staticmethod
    def calculate(final_price):
        commission = final_price * CommissionService.COMMISSION_RATE
        driver_earning = final_price - commission
        return commission, driver_earning