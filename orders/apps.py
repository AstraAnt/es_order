from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(seed_roles, sender=self)

def seed_roles(sender, **kwargs):
    from .models import PartnerRole
    roles = [
        ("supplier", "Supplier"),
        ("buyer", "Buyer"),
        ("manufacturer", "Manufacturer"),
        ("business_unit", "Business Unit"),
    ]
    for code, title in roles:
        PartnerRole.objects.get_or_create(code=code, defaults={"title": title})
