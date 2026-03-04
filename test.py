from uuid import UUID
from datetime import date
from django.utils import timezone

from orders.application.order_service import OrderApplicationService
from orders.infrastructure.event_store import DjangoEventStore
from orders.projections.order_projector import OrderProjector
from orders.domain.commands import CreateOrder
from orders.models import Partner

service = OrderApplicationService(
    event_store=DjangoEventStore(),
    projector=OrderProjector(),
    now_fn=timezone.now
)

oid = UUID("d4bf23b2-17c0-4cdd-8de2-2432019c9c77")

bu = Partner.objects.filter(roles__code="business_unit").first()
buyer = Partner.objects.filter(roles__code="buyer").first()

cmd = CreateOrder(
    order_id=oid,
    human_code="",  # пусть сгенерируется
    date=date(2026, 3, 3),
    business_unit_id=bu.id,
    buyer_id=buyer.id,
    currency_id="RUB",
    notes="тест",
    buyer_commission_percent=None,
    buyer_commission_amount=None,
    buyer_delivery_cost=0,
)

service.create_order(cmd)