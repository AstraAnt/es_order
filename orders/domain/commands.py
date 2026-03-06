from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID


# ---------------------------
# КОМАНДЫ ЗАКАЗА
# ---------------------------

@dataclass(frozen=True)
class CreateOrder:
    """
    Команда: создать заказ.

    Важно:
    - human_code лучше передавать уже сгенерированным на command side.
      Но сервис умеет сгенерировать, если human_code пустой.
    - supplier_id опционален: заказ может появиться до выбора поставщика.
    """
    order_id: UUID
    human_code: str

    date: date
    business_unit_id: UUID          # Partner(role=business_unit) обязателен
    buyer_id: UUID                  # Partner(role=buyer) обязателен

    currency_id: str
    notes: Optional[str] = None

    buyer_commission_percent: Optional[Decimal] = None
    buyer_commission_amount: Optional[Decimal] = None
    buyer_delivery_cost: Decimal = Decimal("0")


@dataclass(frozen=True)
class UpdateOrder:
    """
    Команда: обновить заказ.

    Здесь важен нюанс:
    - supplier_id может быть "не менять"
    - или "установить"
    - или "снять (NULL)"

    Поэтому используем supplier_action:
    - keep  -> игнорируем supplier
    - set   -> supplier_id обязателен
    - unset -> записываем supplier_id = null
    """
    order_id: UUID

    date: Optional[date] = None
    notes: Optional[str] = None

    business_unit_id: Optional[UUID] = None
    buyer_id: Optional[UUID] = None

    business_unit_id: Optional[UUID] = None
    buyer_id: Optional[UUID] = None
    # currency_id: Optional[UUID] = None
    currency_id: Optional[str] = None

    buyer_commission_percent: Optional[Decimal] = None
    buyer_commission_amount: Optional[Decimal] = None
    buyer_delivery_cost: Optional[Decimal] = None

    status: Optional[str] = None


@dataclass(frozen=True)
class CancelOrder:
    """
    Команда: отменить заказ.
    """
    order_id: UUID
    reason: Optional[str] = None


# ---------------------------
# КОМАНДЫ ПОЗИЦИЙ
# ITEMS (BARCODE) ----------

@dataclass(frozen=True)
class AddOrderItem:
    """
    Команда: добавить строку заказа.

    Инвариант:
    - ровно одно из (product_id, planned_product_id) должно быть указано.

    product_id — реальный товар (wb_sku строкой)
    planned_product_id — UUID планового товара
    """
    order_id: UUID
    item_id: UUID

    # Реальный идентификатор товара в заказе — БАРКОД
    product_barcode: Optional[str] = None  # ProductSKU.barcode

    # Плановый товар (если баркода ещё нет)
    planned_product_id: Optional[UUID] = None

    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")

    production_days: int = 0
    delivery_days: int = 14

    planned_fx_to_rub: Optional[Decimal] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class RemoveOrderItem:
    """
    Команда: удалить строку.
    В ES обычно делаем "мягкое" удаление (is_removed=True в проекции).
    """
    order_id: UUID
    item_id: UUID
    reason: Optional[str] = None


@dataclass(frozen=True)
class SetOrderItemQuantity:
    """
    Команда: изменить количество.
    """
    order_id: UUID
    item_id: UUID
    quantity: Decimal


@dataclass(frozen=True)
class SetOrderItemPrice:
    """
    Команда: изменить цену.
    """
    order_id: UUID
    item_id: UUID
    price: Decimal


@dataclass(frozen=True)
class SetOrderItemFxPlanned:
    """
    Команда: изменить плановый курс FX для строки.
    Важно хранить курс явно в событиях, чтобы отчёты были воспроизводимы.
    """
    order_id: UUID
    item_id: UUID
    planned_fx_to_rub: Decimal


@dataclass(frozen=True)
class ResolveOrderItemToProduct:
    """
    Стратегия : planned -> barcode

    Когда появляется реальный SKU (ProductSKU) и его barcode,
    мы "апгрейдим" строку:
      planned_product_id -> NULL
      product_barcode -> <barcode>
    """
    order_id: UUID
    item_id: UUID
    to_product_barcode: str                 # ProductSKU.barcode
    from_planned_product_id: Optional[UUID] = None
    link_id: Optional[UUID] = None