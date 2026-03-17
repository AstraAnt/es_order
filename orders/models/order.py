import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class OrderView(models.Model):
    """
    Read model / проекция заказа.
    """

    order_id = models.UUIDField(primary_key=True)

    # Человекочитаемый номер
    human_code = models.CharField(max_length=255, unique=True, db_index=True)

    # Владелец заказа теперь Business Unit, а не Partner
    business_unit = models.ForeignKey(
        "orders.BusinessUnit",
        on_delete=models.PROTECT,
        related_name="order_views",
    )

    # Buyer остаётся Partner(role=buyer)
    buyer = models.ForeignKey(
        "orders.Partner",
        on_delete=models.PROTECT,
        related_name="order_views_as_buyer",
    )

    currency = models.ForeignKey(
        "finance.Currency",
        on_delete=models.PROTECT,
        related_name="order_views",
    )

    date = models.DateField()
    notes = models.TextField(blank=True, null=True)

    buyer_commission_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    buyer_commission_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    buyer_delivery_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    items_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    status = models.CharField(max_length=30, default="Active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order View"
        verbose_name_plural = "Order Views"
        indexes = [
            models.Index(fields=["human_code"]),
            models.Index(fields=["status", "date"]),
            models.Index(fields=["business_unit", "buyer"]),
        ]

    def clean(self):
        # Buyer должен быть контрагентом с ролью buyer
        if self.buyer_id and not self.buyer.has_role("buyer"):
            raise ValidationError({"buyer": "У партнёра нет роли Buyer."})

        if self.buyer_commission_percent is not None and self.buyer_commission_amount is not None:
            raise ValidationError("Комиссия buyer: укажите либо процент, либо сумму.")

    def __str__(self):
        return self.human_code


class OrderItemView(models.Model):
    """
    Read model строк заказа.
    """
    item_id = models.UUIDField(primary_key=True)
    order_id = models.UUIDField(db_index=True)

    # Реальный товар определяется по barcode
    product_barcode = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    planned_product_id = models.UUIDField(null=True, blank=True)

    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    production_days = models.IntegerField(default=0)
    delivery_days = models.IntegerField(default=14)

    planned_fx_to_rub = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    is_removed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order Item View"
        verbose_name_plural = "Order Item Views"
        indexes = [
            models.Index(fields=["order_id", "is_removed"]),
            models.Index(fields=["product_barcode"]),
        ]

    @property
    def subtotal(self) -> Decimal:
        return self.quantity * self.price


class PurchaseOrder(models.Model):
    """
    Materialized write model заказа (опционально).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    human_code = models.CharField(max_length=255, unique=True, db_index=True)
    date = models.DateField()

    business_unit = models.ForeignKey(
        "orders.BusinessUnit",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    buyer = models.ForeignKey(
        "orders.Partner",
        on_delete=models.PROTECT,
        related_name="purchase_orders_as_buyer",
    )

    currency = models.ForeignKey(
        "finance.Currency",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    notes = models.TextField(blank=True, null=True)

    buyer_commission_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    buyer_commission_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    buyer_delivery_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=30, default="Active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Purchase Order"
        verbose_name_plural = "Purchase Orders"

    def clean(self):
        if self.buyer_id and not self.buyer.has_role("buyer"):
            raise ValidationError({"buyer": "У партнёра нет роли Buyer."})

        if self.buyer_commission_percent is not None and self.buyer_commission_amount is not None:
            raise ValidationError("Комиссия buyer: либо percent, либо amount.")
        if self.buyer_commission_percent is not None and self.buyer_commission_percent < 0:
            raise ValidationError("Комиссия % не может быть отрицательной.")
        if self.buyer_commission_amount is not None and self.buyer_commission_amount < 0:
            raise ValidationError("Комиссия суммой не может быть отрицательной.")
        if self.buyer_delivery_cost is not None and self.buyer_delivery_cost < 0:
            raise ValidationError("Доставка не может быть отрицательной.")

    def __str__(self):
        return self.human_code


class OrderItem(models.Model):
    """
    Materialized write model строки заказа.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")

    product_sku = models.ForeignKey(
        "orders.ProductSKU",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
        help_text="Конкретный вариант товара по баркоду",
    )

    planned_product = models.ForeignKey(
        "orders.PlannedProduct",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
        help_text="Плановый товар, который позже будет сопоставлен с баркодом",
    )

    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    production_days = models.IntegerField(default=0)
    delivery_days = models.IntegerField(default=14)

    planned_fx_to_rub = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(product_sku__isnull=False) & Q(planned_product__isnull=True)) |
                    (Q(product_sku__isnull=True) & Q(planned_product__isnull=False))
                ),
                name="order_item_exactly_one_product_ref_barcode",
            )
        ]