from rest_framework import serializers
from apps.wallet.models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "wallet"
            "amount",
            "gross_amount",
            "type",
            "reference",
            "description",
            "platform_fee",
        ]
        read_only_fields = [
            "id",
            "type",
            "wallet",
            "amount",
            "gross_amount"
        ]