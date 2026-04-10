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
    - human_code можно передать уже готовым вручную
    - если human_code пустой, application service сгенерирует его автоматически
    - business_unit_id теперь указывает на BusinessUnit
    - buyer_id указывает на Partner с ролью buyer
    """
    order_id: UUID
    human_code: str

    date: date

    # Внутренний бизнес-юнит холдинга
    business_unit_id: UUID

    # Контрагент-баер
    buyer_id: UUID

    # Currency.code, например "RUB" / "USD" / "CNY"
    currency_id: str

    notes: Optional[str] = None

    # Комиссия buyer на весь заказ:
    # либо %, либо сумма, либо ничего
    buyer_commission_percent: Optional[Decimal] = None
    buyer_commission_amount: Optional[Decimal] = None

    # Общая доставка до buyer в валюте заказа
    buyer_delivery_cost: Decimal = Decimal("0")


@dataclass(frozen=True)
class UpdateOrder:
    """
    Команда: обновить заказ.

    Частичное обновление шапки заказа.
    Передаём только те поля, которые хотим изменить.
    """
    order_id: UUID

    date: Optional[date] = None
    notes: Optional[str] = None

    # BusinessUnit
    business_unit_id: Optional[UUID] = None

    # Partner(role=buyer)
    buyer_id: Optional[UUID] = None

    # Currency.code
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
# КОМАНДЫ ПОЗИЦИЙ ЗАКАЗА
# ---------------------------

@dataclass(frozen=True)
class AddOrderItem:
    """
    Команда: добавить строку заказа.

    Инвариант:
    - должно быть указано ровно одно:
        product_barcode
        planned_product_id

    product_barcode — реальный товар через ProductSKU.barcode
    planned_product_id — ID планового товара
    """
    order_id: UUID
    item_id: UUID

    # Реальный товар в заказе определяется barcode
    product_barcode: Optional[str] = None  # ProductSKU.barcode

    # Плановый товар, если barcode ещё не известен
    planned_product_id: Optional[int] = None

    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")

    production_days: int = 0
    delivery_days: int = 14

    planned_fx_to_rub: Optional[Decimal] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class RemoveOrderItem:
    """
    Команда: удалить строку заказа.

    В ES обычно это "мягкое удаление":
    - в событиях появляется OrderItemRemoved
    - в проекции строка помечается как is_removed=True
    """
    order_id: UUID
    item_id: UUID
    reason: Optional[str] = None


@dataclass(frozen=True)
class SetOrderItemQuantity:
    """
    Команда: изменить количество в строке заказа.
    """
    order_id: UUID
    item_id: UUID
    quantity: Decimal


@dataclass(frozen=True)
class SetOrderItemPrice:
    """
    Команда: изменить цену в строке заказа.
    """
    order_id: UUID
    item_id: UUID
    price: Decimal


@dataclass(frozen=True)
class SetOrderItemFxPlanned:
    """
    Команда: изменить плановый курс FX для строки.

    Важно:
    - planned_fx_to_rub хранится в событиях явно
    - это нужно для воспроизводимости отчётов и планов
    """
    order_id: UUID
    item_id: UUID
    planned_fx_to_rub: Decimal


@dataclass(frozen=True)
class ResolveOrderItemToBarcode:
    """
    Команда: перевести строку заказа из planned -> barcode.

    Когда появляется реальный SKU (ProductSKU) и его barcode,
    мы "апгрейдим" строку:
      planned_product_id -> NULL
      product_barcode -> <barcode>
    """
    order_id: UUID
    item_id: UUID

    # ProductSKU.barcode
    to_product_barcode: str

    # Доп. проверка, что резолвим именно тот planned, который ожидали
    from_planned_product_id: Optional[int] = None

    # Опциональная ссылка на ProductLink / аудит
    link_id: Optional[UUID] = None
