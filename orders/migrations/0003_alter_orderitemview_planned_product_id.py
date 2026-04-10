from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_businessunit_businessunitmarketplacetoken_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderitemview",
            name="planned_product_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
