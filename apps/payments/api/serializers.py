from rest_framework import serializers
from apps.payments.models import Transaction


class CreatePaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(
        choices=[choice[0] for choice in Transaction.PAYMENT_METHODS]
    )
