from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from orders.models import BusinessUnit
from orders.session import (
    get_active_business_unit,
    get_user_available_business_units,
    set_active_business_unit,
    user_can_access_business_unit,
)


@login_required
def select_business_unit_page(request):
    """
    Страница выбора активного Business Unit.

    Логика:
    - если пользователь выбирает конкретный BU -> сохраняем его id в сессии
    - если пользователь выбирает "все" / "не выбрано" -> сохраняем None
    """
    available = get_user_available_business_units(request.user)

    if request.method == "POST":
        raw_bu_id = (request.POST.get("business_unit_id") or "").strip()

        # Пустое значение = режим без выбранного BU
        if not raw_bu_id:
            set_active_business_unit(request, None)
            return redirect("orders_list_page")

        if not user_can_access_business_unit(request.user, raw_bu_id):
            return render(request, "orders/select_business_unit.html", {
                "available_business_units": available,
                "active_business_unit": get_active_business_unit(request),
                "error": "У вас нет доступа к выбранному Business Unit.",
            })

        set_active_business_unit(request, raw_bu_id)
        return redirect("orders_list_page")

    return render(request, "orders/select_business_unit.html", {
        "available_business_units": available,
        "active_business_unit": get_active_business_unit(request),
    })