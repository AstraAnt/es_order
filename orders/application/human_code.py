from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone

from orders.models.order import PurchaseOrder


@transaction.atomic
def generate_human_code(*, business_unit_code: str, buyer_code: str, dt: Optional[datetime] = None) -> str:
    """
    Генерация human_code в формате:
      BU_BUYER_27.02.26[_N]

    Части:
    - business_unit_code: Partner.short_code (1–3 символа, уже нормализовано)
    - buyer_code: Partner.short_code (1–3 символа, уже нормализовано)
    - дата: ДД.ММ.ГГ
    - если такой префикс уже есть, добавляем _2, _3 и т.д.

    Важное:
    - atomic + select_for_update защищают от гонок при генерации.
    - уникальность human_code должна быть в БД (unique=True).
    """
    dt = dt or timezone.now()
    date_part = dt.strftime("%d.%m.%y")

    bu = (business_unit_code or "").upper()
    by = (buyer_code or "").upper()
    base = f"{bu}_{by}_{date_part}"

    existing = PurchaseOrder.objects.select_for_update().filter(human_code__startswith=base).count()
    return base if existing == 0 else f"{base}_{existing + 1}"