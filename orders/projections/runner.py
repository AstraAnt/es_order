from typing import List
from django.db import transaction
from orders.models import Event, ProjectorCheckpoint

class ProjectorRunner:
    """
    Раннер проекторов:
    - чекпоинт (idempotency)
    - догонка пачками
    """

    def __init__(self, projector_name: str, project_func):
        self.projector_name = projector_name
        self.project_func = project_func

    def _load_checkpoint(self) -> ProjectorCheckpoint:
        cp, _ = ProjectorCheckpoint.objects.get_or_create(projector_name=self.projector_name)
        return cp

    def _events_after_checkpoint(self, cp: ProjectorCheckpoint, batch_size: int) -> List[Event]:
        qs = Event.objects.all().order_by("occurred_at", "id")
        if cp.last_occurred_at is None or cp.last_event_id is None:
            return list(qs[:batch_size])

        later_time = Event.objects.filter(occurred_at__gt=cp.last_occurred_at)
        same_time_later_id = Event.objects.filter(occurred_at=cp.last_occurred_at, id__gt=cp.last_event_id)
        return list(later_time.union(same_time_later_id).order_by("occurred_at", "id")[:batch_size])

    @transaction.atomic
    def run_batch(self, batch_size: int = 500) -> int:
        cp = self._load_checkpoint()
        events = self._events_after_checkpoint(cp, batch_size=batch_size)
        if not events:
            return 0

        for e in events:
            self.project_func(e)
            cp.last_occurred_at = e.occurred_at
            cp.last_event_id = e.id
            cp.save(update_fields=["last_occurred_at", "last_event_id"])
        return len(events)

    def run_until_caught_up(self, batch_size: int = 500, max_batches: int = 1000) -> int:
        total = 0
        for _ in range(max_batches):
            n = self.run_batch(batch_size=batch_size)
            total += n
            if n == 0:
                break
        return total

    def project_events(self, events: List[Event]) -> None:
        for e in events:
            self.project_func(e)
