import uuid
from django.db import models
from django.utils import timezone


class Event(models.Model):
    """
    Append-only EventStore (таблица событий).

    Важные принципы:
    1) Append-only: события НЕ обновляем и НЕ удаляем, только добавляем.
    2) Один агрегат (заказ) = один поток событий (stream):
         (aggregate_type="PurchaseOrder", aggregate_id=<UUID заказа>)
    3) aggregate_version — версия внутри stream (1..N), нужна для:
       - правильного восстановления состояния (реплей по версии)
       - optimistic concurrency (защита от конкурентных записей)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Тип агрегата. Для заказов используем фиксированно "PurchaseOrder".
    aggregate_type = models.CharField(max_length=50)

    # Идентификатор агрегата: UUID заказа.
    aggregate_id = models.UUIDField(db_index=True)

    # Версия события внутри потока агрегата (1..N).
    aggregate_version = models.PositiveIntegerField()

    # Тип доменного события (OrderCreated, OrderItemAdded, ...)
    event_type = models.CharField(max_length=100)

    # Время наступления события (для догонки проекторов / аудита).
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Полезная нагрузка события (всё, что нужно для восстановления).
    payload = models.JSONField()

    # Метаданные (кто/откуда инициировал, correlation_id, request_id, ip и т.п.)
    metadata = models.JSONField(default=dict)

    class Meta:
        # Запрещаем две записи с одной версией в одном stream
        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_type", "aggregate_id", "aggregate_version"],
                name="uniq_stream_version",
            )
        ]
        indexes = [
            models.Index(fields=["aggregate_type", "aggregate_id", "aggregate_version"]),
            models.Index(fields=["event_type", "occurred_at"]),
        ]


class ProjectorCheckpoint(models.Model):
    """
    Чекпоинт проектора (опционально, для "догонки" событий).

    Идея:
    - Проектор читает события пачками и обновляет read-модели.
    - Чтобы не начинать каждый раз с нуля, храним позицию (last_occurred_at, last_event_id).
    - Сортируем события по (occurred_at, id) — детерминированно.
    """
    projector_name = models.CharField(max_length=100, primary_key=True)

    # Последнее обработанное occurred_at
    last_occurred_at = models.DateTimeField(null=True, blank=True)

    # Последнее обработанное id (второй ключ при одинаковом occurred_at)
    last_event_id = models.UUIDField(null=True, blank=True)
