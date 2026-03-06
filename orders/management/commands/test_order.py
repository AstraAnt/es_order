from datetime import date
from decimal import Decimal
from uuid import UUID
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.application.order_service import OrderApplicationService
from orders.infrastructure.event_store import DjangoEventStore
from orders.projections.order_projector import OrderProjector
from orders.domain.commands import CreateOrder
from orders.models import Partner, Event, OrderView


class Command(BaseCommand):
    help = "Тестовое создание заказа через новый ES application service"

    def handle(self, *args, **options):
        service = OrderApplicationService(
            event_store=DjangoEventStore(),
            projector=OrderProjector(),
            now_fn=timezone.now,
        )

        # Берём первого доступного business_unit и buyer
        bu = Partner.objects.filter(roles__code="business_unit").first()
        buyer = Partner.objects.filter(roles__code="buyer").first()

        if not bu:
            self.stderr.write(self.style.ERROR("Не найден Partner с ролью business_unit"))
            return

        if not buyer:
            self.stderr.write(self.style.ERROR("Не найден Partner с ролью buyer"))
            return

        # oid = UUID("d4bf23b2-17c0-4cdd-8de2-2432019c9c77")
        oid = uuid4()

        cmd = CreateOrder(
            order_id=oid,
            human_code="",  # пусто -> будет автогенерация
            date=date(2026, 3, 3),
            business_unit_id=bu.id,
            buyer_id=buyer.id,
            currency_id="RUB",
            notes="тестовый заказ из management command",
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