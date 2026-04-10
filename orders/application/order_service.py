from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Callable, List

from django.core.exceptions import ValidationError

from orders.domain.order import Order
from orders.domain.events import DomainEvent
from orders.infrastructure.event_store import DjangoEventStore
from orders.projections.order_projector import OrderProjector

from orders.application.validators import require_business_unit, require_partner_role
from orders.application.human_code import generate_human_code


AGGREGATE_TYPE = "PurchaseOrder"


class OrderApplicationService:
    """
    Application layer (command side).

    Что делает:
    - проверяет сущности, требующие ORM/БД
    - восстанавливает агрегат из EventStore
    - вызывает доменные методы handle_*
    - сохраняет события
    - запускает проектор

    Важно:
    - business_unit -> отдельная модель BusinessUnit
    - buyer -> Partner(role=buyer)
    """

    def __init__(
        self,
        event_store: DjangoEventStore,
        projector: OrderProjector,
        now_fn: Callable[[], datetime] = datetime.utcnow,
    ):
        self.event_store = event_store
        self.projector = projector
        self.now_fn = now_fn

    def _rebuild_aggregate(self, order_id) -> Order:
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
        """
        Создание заказа.

        Сценарии:
        1) human_code пустой -> генерируем автоматически
        2) human_code введён вручную -> валидируем и используем как есть
        """
        bu = require_business_unit(cmd.business_unit_id, "business_unit_id")
        buyer = require_partner_role(cmd.buyer_id, "buyer", "buyer_id")

        # Ручной код -> валидируем
        if cmd.human_code and cmd.human_code.strip():
            human_code = cmd.human_code.strip().upper()

            if len(human_code) > 255:
                raise ValidationError({"human_code": "Код заказа слишком длинный."})

            from orders.models import OrderView
            if OrderView.objects.filter(human_code=human_code).exists():
                raise ValidationError({"human_code": "Такой код заказа уже существует."})

            cmd = replace(cmd, human_code=human_code)

        # Пустой код -> генерируем автоматически
        else:
            cmd = replace(
                cmd,
                human_code=generate_human_code(
                    business_unit_code=bu.short_code,
                    buyer_code=buyer.short_code,
                    dt=cmd.date,
                ),
            )

        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_create(now, cmd)
        self._commit(agg, new_events)

    def update_order(self, cmd) -> None:
        if cmd.business_unit_id is not None:
            require_business_unit(cmd.business_unit_id, "business_unit_id")

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

    # ---------- ITEMS ----------

    def add_item(self, cmd) -> None:
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
        now = self.now_fn()
        agg = self._rebuild_aggregate(cmd.order_id)
        new_events = agg.handle_resolve_item_to_barcode(now, cmd)
        self._commit(agg, new_events)