from orders.session import get_active_business_unit, get_user_available_business_units


def active_business_unit_context(request):
    """
    Даёт шаблонам:
    - текущий выбранный BU
    - список BU, доступных пользователю
    """
    active_bu = get_active_business_unit(request)

    if request.user.is_authenticated:
        available = get_user_available_business_units(request.user)
    else:
        available = []

    return {
        "active_business_unit": active_bu,
        "available_business_units": available,
    }