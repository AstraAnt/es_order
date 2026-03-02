from django.db import transaction
from uuid import UUID
from typing import List

from orders.models import Event
from orders.domain.order import Order
from orders.domain.events import DomainEvent

class ConcurrencyError(Exception):
    pass

def load_order(order_id: UUID) -> Order:
    qs = Event.objects.filter(aggregate_type="Order", aggregate_id=order_id).order_by("aggregate_version")
    order = Order.empty(order_id)
    version = 0
    for e in qs:
        order.apply(e.event_type, e.payload)
        version = e.aggregate_version
    order.state.version = version
    return order

@transaction.atomic
def append_events(order_id: UUID, expected_version: int, events: List[DomainEvent]) -> List[Event]:
    last = (
        Event.objects
        .filter(aggregate_type="Order", aggregate_id=order_id)
        .order_by("-aggregate_version")
        .first()
    )
    current_version = last.aggregate_version if last else 0
    if current_version != expected_version:
        raise ConcurrencyError(f"Ожидали v{expected_version}, но в БД уже v{current_version}")

    saved = []
    v = current_version
    for de in events:
        v += 1
        saved.append(Event.objects.create(
            aggregate_type="Order",
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
    saved = append_events(order_id, expected_version, events)
    runner.project_events(saved)
    return saved
