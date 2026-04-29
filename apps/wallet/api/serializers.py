from rest_framework import serializers
from apps.wallet.models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):

    type = serializers.CharField(source="get_type_display", read_only=True)
    wallet_id = serializers.IntegerField(source="wallet.id", read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "wallet_id",
            "amount",
            "gross_amount",
            "platform_fee",
            "type",
            "reference",
            "description",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "wallet_id",
            "amount",
            "gross_amount",
            "platform_fee",
            "type",
            "reference",
            "description",
            "created_at",
        ]