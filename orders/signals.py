from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def seed_initial_data(sender, **kwargs):
    """
    Сидинг справочников после миграций:
    - PartnerRole (роли партнёров)
    - Currency (RUB/USD/CNY)
    """

    # выполняем только после миграций приложения orders
    if sender.name != "orders":
        return

    from orders.models import PartnerRole
    from finance.models import Currency

    # --- роли ---
    roles = [
        ("supplier", "Supplier"),
        ("buyer", "Buyer"),
        ("business_unit", "Business Unit"),
    ]
    for code, title in roles:
        obj, created = PartnerRole.objects.get_or_create(code=code, defaults={"title": title})
        # если заголовок изменился в коде — обновим
        if not created and obj.title != title:
            obj.title = title
            obj.save()

    # --- валюты ---
    currencies = [
        ("RUB", "Российский рубль", "₽"),
        ("USD", "Доллар США", "$"),
        ("CNY", "Китайский юань", "¥"),
    ]
    for code, name, symbol in currencies:
        obj, created = Currency.objects.get_or_create(
            code=code,
            defaults={"name": name, "symbol": symbol, "is_active": True},
        )
        # если уже есть — поддерживаем актуальными (без дублей)
        changed = False
        if obj.name != name:
            obj.name = name
            changed = True
        if obj.symbol != symbol:
            obj.symbol = symbol
            changed = True
        if not obj.is_active:
            obj.is_active = True
            changed = True
        if changed:
            obj.save()