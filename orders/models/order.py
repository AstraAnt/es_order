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

    # Ровно id заказа (= aggregate_id)
    order_id = models.UUIDField(primary_key=True)

    # человеческий вид BU_BUYER_ДД.ММ.ГГ[_N]
    human_code = models.CharField(max_length=255, unique=True, db_index=True)

    # Владелец заказа: Business Unit (Partner с ролью business_unit) (обязательно)
    business_unit = models.ForeignKey("Partner", on_delete=models.PROTECT, related_name="orders_as_business_unit_views")

    # Исполнитель заказа: Buyer — партнёр с ролью buyer (обязательно)
    buyer = models.ForeignKey("Partner", on_delete=models.PROTECT, related_name="orders_as_buyer_views")

    # Валюта заказа (FK)
    currency = models.ForeignKey("Currency", on_delete=models.PROTECT, related_name="order_views")

    # Дата заказа (бизнес-дата)
    date = models.DateField()

    # Комментарий
    notes = models.TextField(blank=True, null=True)

    # Комиссия buyer (либо %, либо фикс сумма, либо ничего)
    buyer_commission_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    buyer_commission_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Доставка до buyer (общая)
    buyer_delivery_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Итоговые суммы (держим в проекции, чтобы быстро показывать в UI)
    # items_total = SUM(qty * price) по строкам
    # total_amount = items_total + комиссия + доставка
    items_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # Статус заказа (Active/Cancelled/...)
    status = models.CharField(max_length=30, default="Active")

    # created_at — фиксируем момент создания из события OrderCreated
    created_at = models.DateTimeField(default=timezone.now)

    # updated_at — техническое поле, когда проекция обновлялась
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        В read model мы дублируем роль-валидацию, чтобы не хранить мусор.
        Основная проверка должна происходить на command side (application service),
        но эта — дополнительный safety net.
        """

        # Роль BU
        if self.business_unit_id and not self.business_unit.has_role("business_unit"):
            raise ValidationError({"business_unit": "У партнёра нет роли Business Unit."})
        # Роль Buyer
        if self.buyer_id and not self.buyer.has_role("buyer"):
            raise ValidationError({"buyer": "У партнёра нет роли Buyer."})

        # Комиссия не может быть одновременно % и суммой
        if self.buyer_commission_percent is not None and self.buyer_commission_amount is not None:
            raise ValidationError("Комиссия buyer: укажите либо процент, либо сумму.")


class OrderItemView(models.Model):
    """
    Read model (проекция) для строк заказа.

    Зачем отдельная таблица:
    - чтобы быстро показывать состав заказа без реплея событий
    - чтобы быстро считать items_total (SUM(qty*price))
    - чтобы иметь индексы по order_id, product_id и т.п.

    В стратегии B:
    - строка может быть создана с planned_product_id
    - позже мы делаем resolve -> product_id
    """

    # UUID строки заказа (стабильный id — необходим в ES)
    item_id = models.UUIDField(primary_key=True)

    # UUID заказа, к которому относится строка
    order_id = models.UUIDField(db_index=True)

    # Реальный вариант товара: barcode (ProductSKU.barcode)
    product_barcode = models.CharField(max_length=255, null=True, blank=True, db_index=True)


    # Плановый товар (UUID), если реального ещё нет
    planned_product_id = models.UUIDField(null=True, blank=True)

    # Кол-во и цена (в валюте заказа)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    # Плановые сроки
    production_days = models.IntegerField(default=0)
    delivery_days = models.IntegerField(default=14)

    # Плановый FX (курс к RUB) — хранится явно, чтобы отчёты не ломались временем
    planned_fx_to_rub = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    notes = models.TextField(blank=True, null=True)

    # "Удаление" в ES обычно делаем мягким флагом (событие OrderItemRemoved)
    is_removed = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order_id", "is_removed"]),
            models.Index(fields=["product_barcode"]),
        ]
    @property
    def subtotal(self) -> Decimal:
        # стоимость строки
        return self.quantity * self.price


class PurchaseOrder(models.Model):
    """
    Materialized write model (опционально).
    В ES можно не иметь этой таблицы, но часто удобно:
    - для админки
    - для интеграций
    - для некоторых отчётов
    В любом случае, "истина" всё равно в EventStore.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Человеческий номер заказа
    human_code = models.CharField(max_length=255, unique=True, db_index=True)

    date = models.DateField()

    # Business unit (обязателен)
    business_unit = models.ForeignKey("Partner", on_delete=models.PROTECT, related_name="orders_as_business_unit"
    )

    # Buyer (обязателен)
    buyer = models.ForeignKey(
        "Partner", on_delete=models.PROTECT, related_name="orders_as_buyer"
    )

    currency = models.ForeignKey("Currency", on_delete=models.PROTECT, related_name="orders")

    notes = models.TextField(blank=True, null=True)

    buyer_commission_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    buyer_commission_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    buyer_delivery_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=30, default="Active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Проверяем роли партнёров
        if self.business_unit_id and not self.business_unit.has_role("business_unit"):
            raise ValidationError({"business_unit": "У партнёра нет роли Business Unit."})
        if self.buyer_id and not self.buyer.has_role("buyer"):
            raise ValidationError({"buyer": "У партнёра нет роли Buyer."})

        # Проверяем комиссию
        if self.buyer_commission_percent is not None and self.buyer_commission_amount is not None:
            raise ValidationError("Комиссия: либо percent, либо amount.")
        if self.buyer_commission_percent is not None and self.buyer_commission_percent < 0:
            raise ValidationError("Комиссия % не может быть отрицательной.")
        if self.buyer_commission_amount is not None and self.buyer_commission_amount < 0:
            raise ValidationError("Комиссия суммой не может быть отрицательной.")
        if self.buyer_delivery_cost is not None and self.buyer_delivery_cost < 0:
            raise ValidationError("Доставка не может быть отрицательной.")


class OrderItem(models.Model):
    """
    Materialized write model строки заказа (опционально).

    Важно:
    - Строка должна ссылаться ЛИБО на Product, ЛИБО на PlannedProduct.
      Это инвариант и на уровне БД делаем CHECK constraint.
    - on_delete=PROTECT, потому что строки заказа не должны "ломаться",
      если кто-то удалил товар из справочника.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")

    # Реальный товар в заказе — конкретный вариант (SKU) по баркоду
    product_sku = models.ForeignKey(
        "ProductSKU",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
        help_text="Конкретный вариант товара по баркоду",
    )

    # Плановый товар (если баркода ещё нет)
    planned_product = models.ForeignKey(
        "PlannedProduct",
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
        # Жёсткий инвариант: ровно одно заполнено — либо product_sku, либо planned_product
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(product__isnull=False) & Q(planned_product__isnull=True)) |
                    (Q(product__isnull=True) & Q(planned_product__isnull=False))
                ),
                name="order_item_exactly_one_product_ref",
            )
        ]