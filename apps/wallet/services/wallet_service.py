from django.db import transaction, IntegrityError
from decimal import Decimal
from apps.wallet.models import DriverWallet, WalletTransaction


class WalletService:

    @staticmethod
    @transaction.atomic
    def credit_driver(
        driver,
        gross_amount,
        reference,
        description="Shipment earning",
        platform_fee=Decimal("0")
    ):
        try:
            gross_amount = Decimal(str(gross_amount))
            platform_fee = Decimal(str(platform_fee or 0))
        except Exception:
            raise ValueError("Invalid decimal values")

        if gross_amount <= 0:
            raise ValueError("Amount must be positive")

        wallet, _ = DriverWallet.objects.select_for_update().get_or_create(driver=driver)

        if WalletTransaction.objects.filter(reference=reference, type="credit").exists():
            return

        net_amount = gross_amount - platform_fee

        try:
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=net_amount,
                type="credit",
                reference=reference,
                description=description,
                gross_amount=gross_amount,
                platform_fee=platform_fee
            )

            wallet.balance += net_amount
            wallet.save(update_fields=["balance"])

        except IntegrityError:
            return