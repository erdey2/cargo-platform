from django.db import transaction, IntegrityError
from decimal import Decimal
from apps.wallet.models import DriverWallet, WalletTransaction


class WalletService:

    @staticmethod
    @transaction.atomic
    def credit_driver(driver, amount, reference, description="Shipment earning", platform_fee=Decimal("0")):

        amount = Decimal(str(amount))
        platform_fee = Decimal(str(platform_fee))

        if amount <= 0:
            raise ValueError("Amount must be positive")

        wallet, _ = DriverWallet.objects.select_for_update().get_or_create(driver=driver)

        # idempotency safety
        if reference and WalletTransaction.objects.filter(reference=reference, type=WalletTransaction.Type.CREDIT).exists():
            return

        driver_earning = amount - platform_fee

        wallet.balance += driver_earning
        wallet.save(update_fields=["balance"])

        try:
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=driver_earning,
                gross_amount=amount,
                type=WalletTransaction.Type.CREDIT,
                reference=reference,
                description=description,
                platform_fee=platform_fee,
            )
        except IntegrityError:
            raise ValueError("Transaction with this reference already exists")