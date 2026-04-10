from django.db.models.signals import post_migrate
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(post_migrate)
def seed_initial_data(sender, **kwargs):
    """
    Сидинг справочников:
    - PartnerRole
    - Currency

    Business Unit и Partner здесь не сидим автоматически,
    потому что это уже предмет конкретной бизнес-настройки.
    """

    if sender.name != "orders":
        return

    from orders.models import PartnerRole
    from finance.models import Currency

    roles = [
        ("supplier", "Supplier"),
        ("buyer", "Buyer"),
        ("manufacturer", "Manufacturer"),
    ]
    for code, title in roles:
        obj, created = PartnerRole.objects.get_or_create(code=code, defaults={"title": title})
        if not created and obj.title != title:
            obj.title = title
            obj.save()

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


@receiver(connection_created)
def configure_sqlite_connection(sender, connection, **kwargs):
    """
    Небольшая стабилизация SQLite для локальной разработки:
    - busy_timeout даёт время дождаться снятия краткой блокировки
    - WAL уменьшает конфликты между чтением и записью
    - synchronous=NORMAL делает dev-режим менее "хрупким" на Windows
    """
    if connection.vendor != "sqlite":
        return

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout = 20000;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
