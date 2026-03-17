from __future__ import annotations

from typing import Optional

from orders.models import BusinessUnit, UserBusinessUnitAccess


SESSION_KEY_ACTIVE_BU_ID = "active_business_unit_id"


def set_active_business_unit(request, business_unit_id: Optional[str]) -> None:
    """
    Сохраняем выбранный Business Unit в сессии.
    None = "не выбрано", работаем без фильтра.
    """
    request.session[SESSION_KEY_ACTIVE_BU_ID] = business_unit_id


def get_active_business_unit_id(request) -> Optional[str]:
    return request.session.get(SESSION_KEY_ACTIVE_BU_ID)


def get_active_business_unit(request) -> Optional[BusinessUnit]:
    """
    Возвращает активный Business Unit из сессии.
    Если не выбран — None.
    """
    bu_id = get_active_business_unit_id(request)
    if not bu_id:
        return None

    return BusinessUnit.objects.filter(id=bu_id, is_active=True).first()


def get_user_available_business_units(user):
    """
    Возвращает список Business Unit, доступных пользователю.
    """
    if not user.is_authenticated:
        return BusinessUnit.objects.none()

    return (
        BusinessUnit.objects
        .filter(
            is_active=True,
            user_accesses__user=user,
            user_accesses__is_active=True,
        )
        .distinct()
        .order_by("name")
    )


def user_can_access_business_unit(user, business_unit_id) -> bool:
    if not user.is_authenticated:
        return False

    return UserBusinessUnitAccess.objects.filter(
        user=user,
        business_unit_id=business_unit_id,
        is_active=True,
    ).exists()