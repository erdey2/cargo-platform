from rest_framework import serializers
from apps.wallet.models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "amount",
            "type",
            "reference",
            "description",
            "platform_fee",
            "driver_earning",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "type",
            "created_at",
        ]