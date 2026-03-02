import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class OrderView(models.Model):
    """
    Read model / проекция заказа для быстрого чтения в UI.

    В ES мы читаем "состояние" из проекций,
    а источник истины — события.

    Почему отдельная таблица:
    - чтобы не делать реплей событий при каждом запросе.
    - чтобы строить нужные индексы для фильтров/поиска/сортировки.
    """
    order_id = models.UUIDField(primary_key=True)

    human_code = models.CharField(max_length=255, unique=True, db_index=True)

    # FK на Partner (единый справочник). Поставщик определяется ролью.
    supplier = models.ForeignKey("Partner", on_delete=models.PROTECT, related_name="orders_as_supplier")
    order_currency = models.CharField(max_length=3)
    base_currency = models.CharField(max_length=3, default="RUB")
    order_amount = models.DecimalField(max_digits=18, decimal_places=2)

    status = models.CharField(max_length=30, default="Active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Проверка роли поставщика
        if self.supplier_id and not self.supplier.has_role("supplier"):
            raise ValidationError({"supplier": "У выбранного партнёра нет роли Supplier."})


# ---------------------------------------------------------
#  ЗАКАЗ НА ПОКУПКУ
# ---------------------------------------------------------

class PurchaseOrder(models.Model):
    """
    Заказ на закупку товаров.
    Включает:
    - клиента (владелец заказа)
    - партнера (баер, исполнитель)
    - список позиций (OrderItem)
    - разбиения оплаты (PaymentStage)
    """

    order_number = models.CharField(max_length=100, unique=True, help_text="Номер заказа")
    date = models.DateField(help_text="Дата оформления заказа")

    client = models.ForeignKey(
        "Client",
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Клиент — владелец заказа",
    )

    partner = models.ForeignKey(
        "Partner",
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Баер",
        help_text="Баер / исполнитель заказа",
    )

    currency = models.ForeignKey(
        "Currency",
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Базовая валюта заказа",
    )
    notes = models.TextField(blank=True, null=True, help_text="Дополнительная информация по заказу, комментарии")
    # Комиссия баера на весь заказ: либо %, либо фикс, либо ничего (=0)
    buyer_commission_percent = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Комиссия баера в %, применяется ко всей сумме товаров заказа"
    )
    buyer_commission_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Комиссия баера фикс суммой в валюте заказа"
    )

    # доставка до баера (общая) в валюте заказа
    buyer_delivery_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Доставка до баера (если общая) в валюте заказа"
    )


    def clean(self):
        # нельзя одновременно процент и фикс
        if self.buyer_commission_percent and self.buyer_commission_amount:
            raise ValidationError("Комиссия баера: укажите либо процент, либо сумму (одно из двух).")

        if self.buyer_commission_percent is not None and self.buyer_commission_percent < 0:
            raise ValidationError("Комиссия баера (%) не может быть отрицательной.")

        if self.buyer_commission_amount is not None and self.buyer_commission_amount < 0:
            raise ValidationError("Комиссия баера (суммой) не может быть отрицательной.")

    def __str__(self):
        return f"Заказ {self.order_number} ({self.client.name})"
    # -------------------------
    # СУММЫ
    # -------------------------
    @property
    def items_total(self):
        """Сумма товаров по позициям (qty * price), без комиссии/доставок."""
        return sum((i.items_subtotal for i in self.items.all()), Decimal("0"))

    @property
    def buyer_commission_value(self):
        """Комиссия баера в валюте заказа."""
        if self.buyer_commission_amount is not None:
            return self.buyer_commission_amount
        if self.buyer_commission_percent is not None:
            return (self.items_total * self.buyer_commission_percent) / Decimal("100")
        return Decimal("0")

    @property
    def total_amount(self):
        """Итог заказа: товары + комиссия + (опционально) доставка до баера."""
        return self.items_total + self.buyer_commission_value + (self.buyer_delivery_cost or 0)



# ---------------------------------------------------------
#  ПОЗИЦИИ ЗАКАЗА (ТОВАРЫ В ЗАКАЗЕ)
# ---------------------------------------------------------

class OrderItem(models.Model):
    """
    Отдельная товарная позиция в заказе.

    product — когда есть реальный SKU
    planned_product — если SKU пока неизвестен
    (используем один из двух вариантов)
    """

    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Заказ, к которому относится позиция",
    )

    product = models.ForeignKey(
        "Product",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="order_items",
        help_text="Реальный товар (если известен)",
    )

    planned_product = models.ForeignKey(
        "PlannedProduct",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="order_items",
        help_text="Плановый товар (если SKU ещё нет)",
    )

    quantity = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Количество товара, заказано штук",
    )

    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Цена за единицу товара в валюте заказа",
    )

    production_days = models.IntegerField(default=0, help_text="Срок изготовления товара (дней)")
    delivery_days = models.IntegerField(default=14, help_text="Плановый срок доставки до Москвы после изготовления (дней)")


    planned_fx_to_rub = models.DecimalField(
        max_digits=18, decimal_places=6,
        null=True, blank=True,
        help_text="Плановый курс валюты заказа к рублю (базовой валюте)",
    )

    notes = models.TextField(blank=True, null=True, help_text="Комментарии к позиции")

    @property
    def subtotal(self):
        """
        Стоимость позиции = количество * цена (в валюте заказа).
        """
        return self.quantity * self.price

    def __str__(self):
        return f"Позиция заказа {self.order.order_number}"



    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.product and not self.planned_product:
            raise ValidationError("Укажите либо реальный товар, либо плановый")
        if self.product and self.planned_product:
            raise ValidationError("Можно указать только один тип товара")

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(product__isnull=False) & Q(planned_product__isnull=True)) |
                    (Q(product__isnull=True) & Q(planned_product__isnull=False))
                ),
                name="order_item_exactly_one_product_ref",
            )
        ]
