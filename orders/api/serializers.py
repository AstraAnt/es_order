from rest_framework import serializers

class CreateOrderSerializer(serializers.Serializer):

    supplier_id = serializers.UUIDField()
    order_currency = serializers.ChoiceField(choices=["USD", "CNY", "RUB"])
    order_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    base_currency = serializers.ChoiceField(choices=["RUB", "USD", "CNY"], default="RUB")

class UpdateOrderSerializer(serializers.Serializer):

    supplier_id = serializers.UUIDField(required=False, allow_null=True)
    order_currency = serializers.ChoiceField(choices=["USD", "CNY", "RUB"], required=False, allow_null=True)
    order_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True, allow_blank=True)

class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)