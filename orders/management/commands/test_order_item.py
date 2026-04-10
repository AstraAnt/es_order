from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.application.order_service import OrderApplicationService
from orders.domain.commands import AddOrderItem, CreateOrder
from orders.infrastructure.event_store import DjangoEventStore
from orders.models import (
    Brand,
    BusinessUnit,
    Category,
    Event,
    OrderItemView,
    OrderView,
    Partner,
    Product,
    ProductSKU,
)
from orders.projections.order_projector import OrderProjector


class Command(BaseCommand):
    help = "Тест: создать заказ, добавить в него строку по barcode и проверить totals"

    def handle(self, *args, **options):
        service = OrderApplicationService(
            event_store=DjangoEventStore(),
            projector=OrderProjector(),
            now_fn=timezone.now,
        )

        bu = BusinessUnit.objects.filter(is_active=True).first()
        buyer = Partner.objects.filter(roles__code="buyer", is_active=True).first()

        if not bu:
            self.stderr.write(self.style.ERROR("Не найден BusinessUnit"))
            return

        if not buyer:
            self.stderr.write(self.style.ERROR("Не найден Partner с ролью buyer"))
            return

        brand, _ = Brand.objects.get_or_create(name="TEST_BRAND")
        category, _ = Category.objects.get_or_create(name="TEST_CATEGORY")

        product, _ = Product.objects.get_or_create(
            wb_sku="WB_TEST_001",
            defaults={
                "seller_sku": "TEST_SELLER_SKU",
                "brand": brand,
                "category": category,
            },
        )

        sku, _ = ProductSKU.objects.get_or_create(
            barcode="TEST_BARCODE_001",
            defaults={
                "product": product,
                "tech_size": "42",
                "wb_size": "42",
                "color": "Black",
            },
        )

        order_id = uuid4()

        create_cmd = CreateOrder(
            order_id=order_id,
            human_code="",
            date=date.today(),
            business_unit_id=bu.id,
            buyer_id=buyer.id,
            currency_id="RUB",
            notes="тест заказа со строкой",
            buyer_commission_percent=Decimal("5.00"),
            buyer_commission_amount=None,
            buyer_delivery_cost=Decimal("10.00"),
        )
        service.create_order(create_cmd)

        item_id = uuid4()

        add_item_cmd = AddOrderItem(
            order_id=order_id,
            item_id=item_id,
            product_barcode=sku.barcode,
            planned_product_id=None,
            quantity=Decimal("2"),
            price=Decimal("100.00"),
            production_days=3,
            delivery_days=10,
            planned_fx_to_rub=None,
            notes="тестовая строка по баркоду",
        )
        service.add_item(add_item_cmd)

        self.stdout.write(self.style.SUCCESS("Заказ и строка созданы"))
        self.stdout.write(f"order_id = {order_id}")
        self.stdout.write(f"item_id = {item_id}")

        ov = OrderView.objects.get(order_id=order_id)
        iv = OrderItemView.objects.get(item_id=item_id)

        self.stdout.write(f"human_code = {ov.human_code}")
        self.stdout.write(f"items_total = {ov.items_total}")
        self.stdout.write(f"total_amount = {ov.total_amount}")
        self.stdout.write(f"item_barcode = {iv.product_barcode}")

        events = list(
            Event.objects.filter(aggregate_id=order_id)
            .order_by("aggregate_version")
            .values_list("aggregate_version", "event_type")
        )
        self.stdout.write(f"События: {events}")
