from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Callable, List
from uuid import UUID

from orders.domain.order import Order
from orders.domain.events import DomainEvent
from orders.infrastructure.event_store import DjangoEventStore
from orders.projections.order_projector import OrderProjector

from orders.application.validators import require_partner_role
from orders.application.human_code import generate_human_code


AGGREGATE_TYPE = "PurchaseOrder"


class OrderApplicationService:
    """
    Application слой (command side).

    Что делает:
    1) Проверяет то, что требует БД:
       - роли partner (BU и Buyer)
       - (при желании) существование ProductSKU по barcode (можно добавить тут)
    2) Восстанавливает агрегат из событий (реплей)
    3) Вызывает доменные методы handle_* -> получаем новые события
    4) Сохраняет события в EventStore
    5) Обновляет read-модели через проектор
    """

    def __init__(self, event_store: DjangoEventStore, projector: OrderProjector, now_fn: Callable[[], datetime] = datetime.utcnow):
        self.event_store = event_store
        self.projector = projector
        self.now_fn = now_fn

    def _rebuild_aggregate(self, order_id: UUID) -> Order:
        events = self.event_store.load_stream(AGGREGATE_TYPE, order_id)
        agg = Order.empty(order_id)
        for e in events:
            agg.apply(e.event_type, e.payload)
        return agg

    def _commit(self, agg: Order, new_events: List[DomainEvent]) -> None:
        expected_version = agg.state.version
        self.event_store.append(AGGREGATE_TYPE, agg.state.order_id, expected_version, new_events)
        self.projector.project(new_events)

    # ---------- ORDER ----------

    def create_order(self, cmd) -> None:
        bu = require_partner_role(cmd.business_unit_id, "business_unit", "business_unit_id")
        buyer = require_partner_role(cmd.buyer_id, "buyer", "buyer_id")

        if not cmd.human_code:
            cmd = replace(cmd, human_code=generate_human_code(
                business_unit_code=bu.short_code,
                buyer_code=buyer.short_code,
            ))

        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_create(now, cmd)
        self._commit(agg, new_events)

    def update_order(self, cmd) -> None:
        if cmd.business_unit_id is not None:
            require_partner_role(cmd.business_unit_id, "business_unit", "business_unit_id")
        if cmd.buyer_id is not None:
            require_partner_role(cmd.buyer_id, "buyer", "buyer_id")

        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_update(now, cmd)
        self._commit(agg, new_events)

    def cancel_order(self, cmd) -> None:
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_cancel(now, cmd)
        self._commit(agg, new_events)

    # ---------- ITEMS (BARCODE) ----------

    def add_item(self, cmd) -> None:
        """
        Здесь (опционально) можно добавить строгую проверку:
        - если cmd.product_barcode != None, убедиться, что ProductSKU(barcode) существует.
        Это типичная ORM-проверка уровня application слоя.
        """
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_add_item(now, cmd)
        self._commit(agg, new_events)

    def remove_item(self, cmd) -> None:
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_remove_item(now, cmd)
        self._commit(agg, new_events)

    def set_item_qty(self, cmd) -> None:
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_set_item_qty(now, cmd)
        self._commit(agg, new_events)

    def set_item_price(self, cmd) -> None:
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_set_item_price(now, cmd)
        self._commit(agg, new_events)

    def set_item_fx_planned(self, cmd) -> None:
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_set_item_fx_planned(now, cmd)
        self._commit(agg, new_events)

    def resolve_item_to_barcode(self, cmd) -> None:
        """
        planned -> barcode.
        Здесь также можно проверить, что barcode существует в ProductSKU.
        """
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_resolve_item_to_barcode(now, cmd)
        self._commit(agg, new_events)