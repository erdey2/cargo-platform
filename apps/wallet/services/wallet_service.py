from django.db import transaction
from decimal import Decimal
from apps.wallet.models import DriverWallet, WalletTransaction


class WalletService:

    @staticmethod
    @transaction.atomic
    def credit_driver(driver, amount, reference, description="Shipment earning", platform_fee=Decimal("0")):

        try:
            amount = Decimal(str(amount))
            platform_fee = Decimal(str(platform_fee or 0))
        except Exception:
            raise ValueError("Invalid decimal values")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Idempotency (better still: enforce DB unique constraint)
        if WalletTransaction.objects.filter(reference=reference, type="credit").exists():
            return

        wallet, _ = DriverWallet.objects.select_for_update().get_or_create(driver=driver)

        driver_earning = amount - platform_fee

        wallet.balance += driver_earning
        wallet.save(update_fields=["balance"])

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            type="credit",
            reference=reference,
            description=description,
            platform_fee=platform_fee,
            driver_earning=driver_earning
        )