from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.application.order_service import OrderApplicationService
from orders.infrastructure.event_store import DjangoEventStore
from orders.projections.order_projector import OrderProjector
from orders.domain.commands import CreateOrder
from orders.models import BusinessUnit, Partner, Event, OrderView


class Command(BaseCommand):
    help = "Тестовое создание заказа через новый ES application service"

    def handle(self, *args, **options):
        service = OrderApplicationService(
            event_store=DjangoEventStore(),
            projector=OrderProjector(),
            now_fn=timezone.now,
        )

        # --- ВАЖНО: теперь BusinessUnit ---
        bu = BusinessUnit.objects.first()

        # buyer остаётся Partner
        buyer = Partner.objects.filter(roles__code="buyer").first()

        if not bu:
            self.stderr.write(self.style.ERROR("Не найден BusinessUnit"))
            return

        if not buyer:
            self.stderr.write(self.style.ERROR("Не найден Partner с ролью buyer"))
            return

        oid = uuid4()

        cmd = CreateOrder(
            order_id=oid,
            human_code="",  # автогенерация
            date=date(2026, 3, 3),
            business_unit_id=bu.id,
            buyer_id=buyer.id,
            currency_id="RUB",
            notes="тестовый заказ",
            buyer_commission_percent=None,
            buyer_commission_amount=None,
            buyer_delivery_cost=Decimal("0"),
        )

        service.create_order(cmd)

        self.stdout.write(self.style.SUCCESS("Заказ создан"))

        events = list(
            Event.objects.filter(aggregate_id=oid)
            .order_by("aggregate_version")
            .values_list("aggregate_version", "event_type")
        )
        self.stdout.write(f"События: {events}")

        ov = OrderView.objects.filter(order_id=oid).first()
        if ov:
            self.stdout.write(f"OrderView.human_code = {ov.human_code}")
        else:
            self.stdout.write(self.style.WARNING("OrderView не найден"))
