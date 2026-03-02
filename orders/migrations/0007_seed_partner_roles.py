from django.db import migrations


def seed_partner_roles(apps, schema_editor):
    PartnerRole = apps.get_model("orders", "PartnerRole")
    Partner = apps.get_model("orders", "Partner")

    # Partner.Role.choices недоступен через apps.get_model безопасно,
    # поэтому перечисляем коды/названия прямо здесь (канонично как в TextChoices)
    roles = [
        ("supplier", "Supplier"),
        ("buyer", "Buyer"),
        ("manufacturer", "Manufacturer"),
        ("business_unit", "Business Unit"),
    ]

    for code, title in roles:
        obj, created = PartnerRole.objects.get_or_create(code=code, defaults={"title": title})
        if not created and obj.title != title:
            obj.title = title
            obj.save(update_fields=["title"])


def unseed_partner_roles(apps, schema_editor):
    PartnerRole = apps.get_model("orders", "PartnerRole")
    PartnerRole.objects.filter(code__in=["supplier", "buyer", "manufacturer", "business_unit"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0006_plannedproduct_productlink"),  # <-- замените на вашу последнюю миграцию
    ]

    operations = [
        migrations.RunPython(seed_partner_roles, unseed_partner_roles),
    ]