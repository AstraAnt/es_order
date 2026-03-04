# orders/services/order_service.py

from __future__ import annotations

from typing import List
from uuid import UUID

from django.db import transaction

from orders.models import Event
from orders.domain.order import Order
from orders.domain.events import DomainEvent
from orders.projections.order_projector import project_order_event


AGGREGATE_TYPE = "PurchaseOrder"


class ConcurrencyError(Exception):
    """Optimistic concurrency: версия в БД изменилась."""
    pass


def load_order(order_id: UUID) -> Order:
    """
    Совместимость: загрузка агрегата через реплей событий.

    Важно:
    - в новой модели aggregate_type = "PurchaseOrder"
    - Order.apply(...) сам увеличивает state.version на каждое событие
    """
    qs = (
        Event.objects
        .filter(aggregate_type=AGGREGATE_TYPE, aggregate_id=order_id)
        .order_by("aggregate_version")
    )
    order = Order.empty(order_id)
    for e in qs:
        order.apply(e.event_type, e.payload)
    return order


@transaction.atomic
def append_events(order_id: UUID, expected_version: int, events: List[DomainEvent]) -> List[Event]:
    """
    Совместимость: записывает доменные события в EventStore как строки таблицы Event.

    expected_version — это order.state.version ДО генерации новых событий.
    """
    last = (
        Event.objects
        .filter(aggregate_type=AGGREGATE_TYPE, aggregate_id=order_id)
        .order_by("-aggregate_version")
        .first()
    )
    current_version = int(last.aggregate_version) if last else 0

    if current_version != expected_version:
        raise ConcurrencyError(f"Ожидали v{expected_version}, но в БД уже v{current_version}")

    saved: List[Event] = []
    v = current_version

    for de in events:
        v += 1
        saved.append(Event.objects.create(
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=order_id,
            aggregate_version=v,
            event_type=de.event_type,
            occurred_at=de.occurred_at,
            payload=de.payload,
            metadata=de.metadata,
        ))

    return saved


@transaction.atomic
def append_and_project(runner, order_id: UUID, expected_version: int, events: List[DomainEvent]) -> List[Event]:
    """
    Совместимость: старый код ждёт append_and_project(runner,...)

    Теперь:
    - события сохраняем
    - проекцию применяем через runner.project_events(...)
      (а runner в итоге вызывает project_order_event, который мы вернули обратно)
    """
    saved = append_events(order_id, expected_version, events)
    if runner is not None:
        runner.project_events(saved)
    else:
        # если runner не передан, всё равно обновим проекцию
        for e in saved:
            project_order_event(e)
    return saved