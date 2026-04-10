import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_alter_orderitemview_planned_product_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="business_unit",
            field=models.ForeignKey(
                blank=True,
                help_text="Business Unit, из которого загружен товар",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="orders.businessunit",
            ),
        ),
    ]
