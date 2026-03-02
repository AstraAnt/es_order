from __future__ import annotations

from uuid import UUID
from django.core.exceptions import ValidationError

from orders.models import Partner


def require_partner_role(partner_id: UUID, role: str, field_name: str) -> Partner:
    """
    Проверяем:
    - партнёр существует
    - партнёр имеет нужную роль
    """
    p = Partner.objects.get(id=partner_id)
    if not p.has_role(role):
        raise ValidationError({field_name: f"У партнёра нет роли {role}."})
    return p