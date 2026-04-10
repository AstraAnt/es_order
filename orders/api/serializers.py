from rest_framework import serializers


# -------------------------
# ORDER
# -------------------------

class CreateOrderSerializer(serializers.Serializer):
    """
    Создание заказа.

    human_code:
    - можно передать вручную
    - можно оставить пустым, тогда он сгенерируется автоматически
    """
    human_code = serializers.CharField(required=False, allow_blank=True)

    date = serializers.DateField()

    business_unit_id = serializers.UUIDField()
    buyer_id = serializers.UUIDField()

    # Currency.code
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


# -------------------------
# ORDER ITEMS
# -------------------------

class AddOrderItemSerializer(serializers.Serializer):
    """
    Добавление строки заказа.

    Должно быть указано ровно одно:
    - product_barcode
    - planned_product_id
    """
    item_id = serializers.UUIDField(required=False)

    product_barcode = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    planned_product_id = serializers.IntegerField(required=False, allow_null=True)

    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)

    production_days = serializers.IntegerField(required=False, default=0)
    delivery_days = serializers.IntegerField(required=False, default=14)

    planned_fx_to_rub = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        barcode = attrs.get("product_barcode")
        planned = attrs.get("planned_product_id")

        has_barcode = bool(barcode)
        has_planned = planned is not None

        if has_barcode == has_planned:
            raise serializers.ValidationError(
                "Нужно указать ровно одно: product_barcode или planned_product_id."
            )
        return attrs


class RemoveOrderItemSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class SetOrderItemQuantitySerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)


class SetOrderItemPriceSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=2)


class SetOrderItemFxPlannedSerializer(serializers.Serializer):
    planned_fx_to_rub = serializers.DecimalField(max_digits=18, decimal_places=6)


class ResolveOrderItemToBarcodeSerializer(serializers.Serializer):
    to_product_barcode = serializers.CharField()
    from_planned_product_id = serializers.IntegerField(required=False, allow_null=True)
    link_id = serializers.UUIDField(required=False, allow_null=True)
