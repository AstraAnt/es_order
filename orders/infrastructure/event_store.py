from __future__ import annotations

from typing import List
from uuid import UUID

from django.db import transaction

from orders.models.event import Event
from orders.domain.events import DomainEvent


class ConcurrencyError(Exception):
    """
    Ошибка optimistic concurrency:
    кто-то успел записать события в этот stream, пока мы работали.
    """
    pass


class DjangoEventStore:
    """
    Инфраструктура EventStore на Django ORM.

    Методы:
    - load_stream: загрузить события агрегата для реплея
    - append: атомарно добавить новые события с проверкой expected_version
    """

    def load_stream(self, aggregate_type: str, aggregate_id: UUID) -> List[Event]:
        return list(
            Event.objects
            .filter(aggregate_type=aggregate_type, aggregate_id=aggregate_id)
            .order_by("aggregate_version")
        )

    def get_current_version(self, aggregate_type: str, aggregate_id: UUID) -> int:
        last = (
            Event.objects
            .filter(aggregate_type=aggregate_type, aggregate_id=aggregate_id)
            .order_by("-aggregate_version")
            .first()
        )
        return int(last.aggregate_version) if last else 0

    @transaction.atomic
    def append(self, aggregate_type: str, aggregate_id: UUID, expected_version: int, domain_events: List[DomainEvent]) -> None:
        current = self.get_current_version(aggregate_type, aggregate_id)
        if current != expected_version:
            raise ConcurrencyError(f"Version mismatch: expected={expected_version}, current={current}")

        version = current
        rows = []
        for de in domain_events:
            version += 1
            rows.append(Event(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                aggregate_version=version,
                event_type=de.event_type,
                occurred_at=de.occurred_at,
                payload=de.payload,
                metadata=de.metadata,
            ))

        Event.objects.bulk_create(rows)