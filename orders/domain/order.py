from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID  # важно: UUID нужен для apply()

from .events import (
    DomainEvent,
    ORDER_CANCELLED,
    ORDER_CREATED,
    ORDER_UPDATED,
    ORDER_ITEM_ADDED,
    ORDER_ITEM_REMOVED,
    ORDER_ITEM_QTY_SET,
    ORDER_ITEM_PRICE_SET,
    ORDER_ITEM_FX_PLANNED_SET,
    ORDER_ITEM_RESOLVED_TO_BARCODE,
)


class DomainError(Exception):
    """Доменные ошибки — инварианты и проверки без доступа к БД."""
    pass


@dataclass
class OrderItemState:
    """
    Состояние одной строки заказа внутри агрегата.

    Важно:
    - Реальный товар идентифицируем barcode (ProductSKU.barcode)
    - Если баркода нет, хранится planned_product_id
    """
    item_id: UUID

    product_barcode: Optional[str] = None
    planned_product_id: Optional[int] = None

    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")

    production_days: int = 0
    delivery_days: int = 14

    planned_fx_to_rub: Optional[Decimal] = None
    notes: Optional[str] = None

    is_removed: bool = False


@dataclass
class OrderState:
    """
    Состояние агрегата заказа.

    version — количество применённых событий (для expected_version при записи).
    """
    order_id: UUID
    version: int = 0

    human_code: str = ""

    date: Optional[date] = None
    business_unit_id: Optional[UUID] = None
    buyer_id: Optional[UUID] = None
    # currency_id: Optional[UUID] = None
    currency_id: Optional[str] = None

    notes: Optional[str] = None

    buyer_commission_percent: Optional[Decimal] = None
    buyer_commission_amount: Optional[Decimal] = None
    buyer_delivery_cost: Decimal = Decimal("0")

    status: str = "Active"

    items: Dict[UUID, OrderItemState] = field(default_factory=dict)


class Order:
    """
    ES агрегат "PurchaseOrder".

    Правило:
    - handle_* возвращает события
    - apply(...) изменяет state, применяя событие (детерминированно)
    """

    def __init__(self, state: OrderState):
        self.state = state

    @staticmethod
    def empty(order_id: UUID) -> "Order":
        return Order(OrderState(order_id=order_id))

    # ----------------- ORDER -----------------

    def handle_create(self, now: datetime, cmd) -> List[DomainEvent]:
        if self.state.version != 0:
            raise DomainError("Заказ уже создан")
        if not cmd.human_code:
            raise DomainError("human_code обязателен")

        # Комиссия: либо %, либо сумма
        if cmd.buyer_commission_percent is not None and cmd.buyer_commission_amount is not None:
            raise DomainError("Комиссия: либо percent, либо amount")
        if cmd.buyer_commission_percent is not None and cmd.buyer_commission_percent < 0:
            raise DomainError("Комиссия % не может быть отрицательной")
        if cmd.buyer_commission_amount is not None and cmd.buyer_commission_amount < 0:
            raise DomainError("Комиссия суммой не может быть отрицательной")
        if cmd.buyer_delivery_cost is not None and cmd.buyer_delivery_cost < 0:
            raise DomainError("Доставка не может быть отрицательной")

        return [DomainEvent(
            event_type=ORDER_CREATED,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={
                "human_code": cmd.human_code,
                "date": cmd.date.isoformat(),

                "business_unit_id": str(cmd.business_unit_id),
                "buyer_id": str(cmd.buyer_id),
                "currency_id": str(cmd.currency_id),

                "notes": cmd.notes,

                # Decimal сериализуем строкой, чтобы не терять точность
                "buyer_commission_percent": str(cmd.buyer_commission_percent) if cmd.buyer_commission_percent is not None else None,
                "buyer_commission_amount": str(cmd.buyer_commission_amount) if cmd.buyer_commission_amount is not None else None,
                "buyer_delivery_cost": str(cmd.buyer_delivery_cost),

                "status": "Active",
            },
            metadata={}
        )]

    def handle_update(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        self._ensure_not_cancelled()

        changes = {}

        if cmd.date is not None:
            changes["date"] = cmd.date.isoformat()
        if cmd.notes is not None:
            changes["notes"] = cmd.notes

        if cmd.business_unit_id is not None:
            changes["business_unit_id"] = str(cmd.business_unit_id)
        if cmd.buyer_id is not None:
            changes["buyer_id"] = str(cmd.buyer_id)
        if cmd.currency_id is not None:
            changes["currency_id"] = str(cmd.currency_id)

        if cmd.buyer_commission_percent is not None and cmd.buyer_commission_amount is not None:
            raise DomainError("Комиссия: либо percent, либо amount")

        if cmd.buyer_commission_percent is not None:
            if cmd.buyer_commission_percent < 0:
                raise DomainError("Комиссия % не может быть отрицательной")
            changes["buyer_commission_percent"] = str(cmd.buyer_commission_percent)
            changes["buyer_commission_amount"] = None

        if cmd.buyer_commission_amount is not None:
            if cmd.buyer_commission_amount < 0:
                raise DomainError("Комиссия суммой не может быть отрицательной")
            changes["buyer_commission_amount"] = str(cmd.buyer_commission_amount)
            changes["buyer_commission_percent"] = None

        if cmd.buyer_delivery_cost is not None:
            if cmd.buyer_delivery_cost < 0:
                raise DomainError("Доставка не может быть отрицательной")
            changes["buyer_delivery_cost"] = str(cmd.buyer_delivery_cost)

        if cmd.status is not None:
            changes["status"] = cmd.status

        if not changes:
            return []

        return [DomainEvent(
            event_type=ORDER_UPDATED,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload=changes,
            metadata={}
        )]

    def handle_cancel(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        if self.state.status == "Cancelled":
            return []

        return [DomainEvent(
            event_type=ORDER_CANCELLED,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={"reason": cmd.reason, "status": "Cancelled"},
            metadata={}
        )]

    # ----------------- ITEMS (BARCODE) -----------------

    def handle_add_item(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        self._ensure_not_cancelled()

        if cmd.item_id in self.state.items and not self.state.items[cmd.item_id].is_removed:
            raise DomainError("Item уже существует")

        # XOR: либо barcode, либо planned
        has_barcode = cmd.product_barcode is not None
        has_planned = cmd.planned_product_id is not None
        if has_barcode == has_planned:
            raise DomainError("Нужно указать ровно одно: product_barcode или planned_product_id")

        if cmd.quantity <= 0:
            raise DomainError("quantity должно быть > 0")
        if cmd.price < 0:
            raise DomainError("price не может быть < 0")

        return [DomainEvent(
            event_type=ORDER_ITEM_ADDED,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={
                "item_id": str(cmd.item_id),

                # ключевое: barcode
                "product_barcode": cmd.product_barcode,
                "planned_product_id": str(cmd.planned_product_id) if cmd.planned_product_id is not None else None,

                "quantity": str(cmd.quantity),
                "price": str(cmd.price),

                "production_days": cmd.production_days,
                "delivery_days": cmd.delivery_days,

                "planned_fx_to_rub": str(cmd.planned_fx_to_rub) if cmd.planned_fx_to_rub is not None else None,
                "notes": cmd.notes,
            },
            metadata={}
        )]

    def handle_remove_item(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        self._ensure_not_cancelled()

        item = self._get_item(cmd.item_id)
        if item.is_removed:
            return []

        return [DomainEvent(
            event_type=ORDER_ITEM_REMOVED,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={"item_id": str(cmd.item_id), "reason": cmd.reason},
            metadata={}
        )]

    def handle_set_item_qty(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        self._ensure_not_cancelled()

        if cmd.quantity <= 0:
            raise DomainError("quantity должно быть > 0")

        item = self._get_item(cmd.item_id)
        if item.quantity == cmd.quantity:
            return []

        return [DomainEvent(
            event_type=ORDER_ITEM_QTY_SET,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={"item_id": str(cmd.item_id), "quantity": str(cmd.quantity)},
            metadata={}
        )]

    def handle_set_item_price(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        self._ensure_not_cancelled()

        if cmd.price < 0:
            raise DomainError("price не может быть < 0")

        item = self._get_item(cmd.item_id)
        if item.price == cmd.price:
            return []

        return [DomainEvent(
            event_type=ORDER_ITEM_PRICE_SET,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={"item_id": str(cmd.item_id), "price": str(cmd.price)},
            metadata={}
        )]

    def handle_set_item_fx_planned(self, now: datetime, cmd) -> List[DomainEvent]:
        self._ensure_exists()
        self._ensure_not_cancelled()

        if cmd.planned_fx_to_rub <= 0:
            raise DomainError("planned_fx_to_rub должно быть > 0")

        item = self._get_item(cmd.item_id)
        if item.planned_fx_to_rub == cmd.planned_fx_to_rub:
            return []

        return [DomainEvent(
            event_type=ORDER_ITEM_FX_PLANNED_SET,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={"item_id": str(cmd.item_id), "planned_fx_to_rub": str(cmd.planned_fx_to_rub)},
            metadata={}
        )]

    def handle_resolve_item_to_barcode(self, now: datetime, cmd) -> List[DomainEvent]:
        """
        Стратегия B: planned -> barcode

        Допущения домена:
        - если строка уже имеет barcode, переклейка запрещена (нужна отдельная команда)
        - строка должна быть planned
        """
        self._ensure_exists()
        self._ensure_not_cancelled()

        item = self._get_item(cmd.item_id)

        if item.product_barcode is not None:
            if item.product_barcode == cmd.to_product_barcode:
                return []
            raise DomainError("Item уже имеет product_barcode; переклейка запрещена")

        if item.planned_product_id is None:
            raise DomainError("Item не planned, resolve невозможен")

        if cmd.from_planned_product_id is not None and item.planned_product_id != cmd.from_planned_product_id:
            raise DomainError("from_planned_product_id не совпадает с текущим planned_product_id позиции")

        return [DomainEvent(
            event_type=ORDER_ITEM_RESOLVED_TO_BARCODE,
            aggregate_id=cmd.order_id,
            occurred_at=now,
            payload={
                "item_id": str(cmd.item_id),
                "from_planned_product_id": str(item.planned_product_id),
                "to_product_barcode": cmd.to_product_barcode,
                "link_id": str(cmd.link_id) if cmd.link_id is not None else None,
            },
            metadata={}
        )]

    # ----------------- APPLY -----------------

    def apply(self, event_type: str, payload: dict) -> None:
        """
        apply() должен быть детерминированным и НЕ ходить в базу.

        Здесь мы:
        - восстанавливаем состояние агрегата
        - увеличиваем version на каждом событии
        """
        if event_type == ORDER_CREATED:
            self.state.human_code = payload["human_code"]
            self.state.date = date.fromisoformat(payload["date"])

            self.state.business_unit_id = UUID(payload["business_unit_id"])
            self.state.buyer_id = UUID(payload["buyer_id"])
            # self.state.currency_id = UUID(payload["currency_id"])
            self.state.currency_id = payload["currency_id"]

            self.state.notes = payload.get("notes")

            bcp = payload.get("buyer_commission_percent")
            bca = payload.get("buyer_commission_amount")
            self.state.buyer_commission_percent = Decimal(bcp) if bcp is not None else None
            self.state.buyer_commission_amount = Decimal(bca) if bca is not None else None
            self.state.buyer_delivery_cost = Decimal(payload.get("buyer_delivery_cost", "0"))

            self.state.status = payload.get("status", "Active")

        elif event_type == ORDER_UPDATED:
            if "date" in payload:
                self.state.date = date.fromisoformat(payload["date"])
            if "notes" in payload:
                self.state.notes = payload["notes"]

            if "business_unit_id" in payload:
                self.state.business_unit_id = UUID(payload["business_unit_id"])
            if "buyer_id" in payload:
                self.state.buyer_id = UUID(payload["buyer_id"])
            if "currency_id" in payload:
                # self.state.currency_id = UUID(payload["currency_id"])
                self.state.currency_id = payload["currency_id"]

            if "buyer_commission_percent" in payload:
                v = payload["buyer_commission_percent"]
                self.state.buyer_commission_percent = Decimal(v) if v is not None else None
            if "buyer_commission_amount" in payload:
                v = payload["buyer_commission_amount"]
                self.state.buyer_commission_amount = Decimal(v) if v is not None else None
            if "buyer_delivery_cost" in payload:
                self.state.buyer_delivery_cost = Decimal(payload["buyer_delivery_cost"])

            if "status" in payload:
                self.state.status = payload["status"]

        elif event_type == ORDER_CANCELLED:
            self.state.status = payload.get("status", "Cancelled")

        elif event_type == ORDER_ITEM_ADDED:
            item_id = UUID(payload["item_id"])
            pp = payload.get("planned_product_id")

            self.state.items[item_id] = OrderItemState(
                item_id=item_id,
                product_barcode=payload.get("product_barcode"),
                planned_product_id=int(pp) if pp is not None else None,
                quantity=Decimal(payload["quantity"]),
                price=Decimal(payload["price"]),
                production_days=int(payload.get("production_days", 0)),
                delivery_days=int(payload.get("delivery_days", 14)),
                planned_fx_to_rub=Decimal(payload["planned_fx_to_rub"]) if payload.get("planned_fx_to_rub") is not None else None,
                notes=payload.get("notes"),
                is_removed=False,
            )

        elif event_type == ORDER_ITEM_REMOVED:
            item_id = UUID(payload["item_id"])
            if item_id in self.state.items:
                self.state.items[item_id].is_removed = True

        elif event_type == ORDER_ITEM_QTY_SET:
            item_id = UUID(payload["item_id"])
            self.state.items[item_id].quantity = Decimal(payload["quantity"])

        elif event_type == ORDER_ITEM_PRICE_SET:
            item_id = UUID(payload["item_id"])
            self.state.items[item_id].price = Decimal(payload["price"])

        elif event_type == ORDER_ITEM_FX_PLANNED_SET:
            item_id = UUID(payload["item_id"])
            self.state.items[item_id].planned_fx_to_rub = Decimal(payload["planned_fx_to_rub"])

        elif event_type == ORDER_ITEM_RESOLVED_TO_BARCODE:
            item_id = UUID(payload["item_id"])
            item = self.state.items[item_id]
            item.product_barcode = payload["to_product_barcode"]
            item.planned_product_id = None

        # Версия агрегата растёт на каждое применённое событие
        self.state.version += 1

    # ----------------- HELPERS -----------------

    def _ensure_exists(self) -> None:
        if self.state.version == 0:
            raise DomainError("Заказ ещё не создан")

    def _ensure_not_cancelled(self) -> None:
        if self.state.status == "Cancelled":
            raise DomainError("Нельзя менять отменённый заказ")

    def _get_item(self, item_id: UUID) -> OrderItemState:
        if item_id not in self.state.items:
            raise DomainError("Item не найден")
        item = self.state.items[item_id]
        if item.is_removed:
            raise DomainError("Item удалён")
        return item
