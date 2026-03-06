from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import F

from orders.models import OrderNumberCounter


def generate_human_code(*, business_unit_code: str, buyer_code: str, dt: Optional[datetime] = None) -> str:
    """
    Атомарная генерация human_code, совместимая с SQLite/PostgreSQL.

    Формат:
      BU_BUYER_27.02.26
      BU_BUYER_27.02.26_2
      BU_BUYER_27.02.26_3
      ...

    Почему именно так:
    - count() по OrderView/Order не атомарен и даёт дубли при конкуренции
    - отдельная таблица OrderNumberCounter хранит последний номер по prefix
    - при высокой конкуренции используем retry через IntegrityError

    Алгоритм:
    1) Пытаемся атомарно увеличить last_number у уже существующего prefix
    2) Если prefix ещё нет — создаём его с last_number=1
    3) Если в момент создания возникла гонка — повторяем цикл

    Этот вариант:
    - работает на SQLite
    - работает на PostgreSQL
    - не требует raw SQL
    """
    from django.utils import timezone

    dt = dt or timezone.now()
    date_part = dt.strftime("%d.%m.%y")

    bu = (business_unit_code or "").upper().strip()
    by = (buyer_code or "").upper().strip()
    prefix = f"{bu}_{by}_{date_part}"

    while True:
        try:
            with transaction.atomic():
                # 1. Пытаемся атомарно увеличить счётчик, если строка уже есть
                updated = (
                    OrderNumberCounter.objects
                    .filter(prefix=prefix)
                    .update(last_number=F("last_number") + 1)
                )

                if updated:
                    # строка уже существовала, теперь получаем новое значение
                    counter = OrderNumberCounter.objects.get(prefix=prefix)
                    number = counter.last_number
                else:
                    # строки ещё нет -> создаём первую
                    counter = OrderNumberCounter.objects.create(
                        prefix=prefix,
                        last_number=1,
                    )
                    number = counter.last_number

                return prefix if number == 1 else f"{prefix}_{number}"

        except IntegrityError:
            # Параллельная транзакция успела создать prefix раньше нас.
            # Просто повторяем попытку.
            continue