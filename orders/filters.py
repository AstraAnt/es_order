from orders.session import get_active_business_unit


def filter_queryset_by_active_business_unit(request, queryset, field_name: str = "business_unit"):
    """
    Универсальный helper для фильтрации queryset по активному BU из сессии.

    Если BU не выбран:
    - возвращаем queryset без фильтра

    Пример:
        qs = filter_queryset_by_active_business_unit(request, OrderView.objects.all())
    """
    active_bu = get_active_business_unit(request)
    if not active_bu:
        return queryset

    return queryset.filter(**{field_name: active_bu})