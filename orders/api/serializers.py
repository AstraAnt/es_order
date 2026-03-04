from rest_framework import serializers


class CreateOrderSerializer(serializers.Serializer):
    """
    Создание заказа.

    Важно:
    - human_code можно не передавать: он будет сгенерирован как BU_BUYER_ДД.ММ.ГГ[_N]
    """
    human_code = serializers.CharField(required=False, allow_blank=True)

    date = serializers.DateField()

    business_unit_id = serializers.UUIDField()
    buyer_id = serializers.UUIDField()

    # Currency у нас PK = code (RUB/USD/...), но в нашем домене/ивентах мы храним currency_id.
    # В твоём проекте Currency.code = primary_key => это строка 3 символа.
    # Поэтому здесь делаем CharField.
    currency_id = serializers.CharField(max_length=3)

    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    buyer_commission_percent = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    buyer_commission_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    buyer_delivery_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0
    )


class UpdateOrderSerializer(serializers.Serializer):
    """
    Частичное обновление заказа.
    """
    date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    business_unit_id = serializers.UUIDField(required=False, allow_null=True)
    buyer_id = serializers.UUIDField(required=False, allow_null=True)
    currency_id = serializers.CharField(required=False, allow_null=True, max_length=3)

    buyer_commission_percent = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    buyer_commission_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    buyer_delivery_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )

    status = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)