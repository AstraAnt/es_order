from django.core.exceptions import ValidationError

from orders.models import BusinessUnit, Partner


def require_business_unit(business_unit_id, field_name: str = "business_unit_id") -> BusinessUnit:
    """
    Проверяем, что Business Unit существует и активен.
    """
    try:
        return BusinessUnit.objects.get(id=business_unit_id, is_active=True)
    except BusinessUnit.DoesNotExist:
        raise ValidationError({field_name: "Business Unit не найден или не активен."})


def require_partner_role(partner_id, role: str, field_name: str) -> Partner:
    """
    Проверяем, что Partner:
    - существует
    - активен
    - имеет нужную роль
    """
    try:
        p = Partner.objects.get(id=partner_id, is_active=True)
    except Partner.DoesNotExist:
        raise ValidationError({field_name: "Partner не найден или не активен."})

    if not p.has_role(role):
        raise ValidationError({field_name: f"У партнёра нет роли {role}."})

    return p