import uuid
from decimal import Decimal
from uuid import UUID

from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from finance.models import Currency
from orders.application.order_service import OrderApplicationService
from orders.domain.commands import CreateOrder, UpdateOrder, CancelOrder
from orders.infrastructure.event_store import DjangoEventStore
from orders.models import OrderView, Event, Partner
from orders.projections.order_projector import OrderProjector

# ВАЖНО: новый aggregate_type для заказов
AGGREGATE_TYPE = "PurchaseOrder"

# ---------------------------------------------------------
# Wiring (простой вариант: "синглтоны" на модуль)
# ---------------------------------------------------------
event_store = DjangoEventStore()
projector = OrderProjector()
service = OrderApplicationService(event_store=event_store, projector=projector, now_fn=timezone.now)


def orders_list_page(request):
    """
    Страница-список всех заказов из OrderView (проекция).
    Быстро, потому что это read-model, а не реплей событий.
    """
    qs = (
        OrderView.objects
        .all()
        .select_related("business_unit", "buyer", "currency")
        .order_by("-updated_at")
    )
    return render(request, "orders/orders_list.html", {"orders": qs})


def order_detail_page(request, order_id):
    """
    Детальная страница одного заказа (проекция OrderView).
    """
    obj = get_object_or_404(
        OrderView.objects.select_related("business_unit", "buyer", "currency"),
        order_id=order_id
    )
    return render(request, "orders/order_detail.html", {"order": obj})


def order_create_page(request):
    """
    HTML страница создания заказа.
    UI над командой CreateOrder.

    Здесь выбираем:
    - business_unit (Partner с ролью business_unit)
    - buyer (Partner с ролью buyer)
    - currency (Currency.code, например RUB/USD/CNY)
    """
    business_units = (
        Partner.objects
        .filter(is_active=True, roles__code="business_unit")
        .distinct()
        .order_by("name")
    )
    buyers = (
        Partner.objects
        .filter(is_active=True, roles__code="buyer")
        .distinct()
        .order_by("name")
    )
    currencies = Currency.objects.filter(is_active=True).order_by("code")

    if request.method == "POST":
        order_id = uuid.uuid4()

        # human_code можно оставить пустым — сгенерируется
        human_code = (request.POST.get("human_code") or "").strip()

        date_str = request.POST["date"]  # yyyy-mm-dd
        business_unit_id = UUID(request.POST["business_unit_id"])
        buyer_id = UUID(request.POST["buyer_id"])
        currency_code = (request.POST["currency_code"] or "").strip().upper()

        notes = (request.POST.get("notes") or "").strip() or None

        raw_percent = (request.POST.get("buyer_commission_percent") or "").strip()
        raw_amount = (request.POST.get("buyer_commission_amount") or "").strip()
        raw_delivery = (request.POST.get("buyer_delivery_cost") or "").strip()

        buyer_commission_percent = Decimal(raw_percent) if raw_percent else None
        buyer_commission_amount = Decimal(raw_amount) if raw_amount else None
        buyer_delivery_cost = Decimal(raw_delivery) if raw_delivery else Decimal("0")

        cmd = CreateOrder(
            order_id=order_id,
            human_code=human_code,

            date=timezone.datetime.fromisoformat(date_str).date(),
            business_unit_id=business_unit_id,
            buyer_id=buyer_id,

            # Currency PK = code => передаём строку "RUB"/"USD"/...
            currency_id=currency_code,

            notes=notes,
            buyer_commission_percent=buyer_commission_percent,
            buyer_commission_amount=buyer_commission_amount,
            buyer_delivery_cost=buyer_delivery_cost,
        )

        service.create_order(cmd)

        return redirect("order_detail_page", order_id=order_id)

    return render(request, "orders/order_create.html", {
        "business_units": business_units,
        "buyers": buyers,
        "currencies": currencies,
        "today": timezone.now().date().isoformat(),
    })


def order_edit_page(request, order_id):
    """
    Форма изменения заказа (UI над командой UpdateOrder).
    """
    obj = get_object_or_404(
        OrderView.objects.select_related("business_unit", "buyer", "currency"),
        order_id=order_id
    )

    business_units = (
        Partner.objects
        .filter(is_active=True, roles__code="business_unit")
        .distinct()
        .order_by("name")
    )
    buyers = (
        Partner.objects
        .filter(is_active=True, roles__code="buyer")
        .distinct()
        .order_by("name")
    )
    currencies = Currency.objects.filter(is_active=True).order_by("code")

    if request.method == "POST":
        # Если заказ отменён — домен всё равно не даст менять (но UI тоже подсветит)
        date_str = (request.POST.get("date") or "").strip() or None
        notes = (request.POST.get("notes") or "").strip()

        raw_bu = (request.POST.get("business_unit_id") or "").strip() or None
        raw_buyer = (request.POST.get("buyer_id") or "").strip() or None
        raw_currency = (request.POST.get("currency_code") or "").strip() or None

        raw_percent = (request.POST.get("buyer_commission_percent") or "").strip()
        raw_amount = (request.POST.get("buyer_commission_amount") or "").strip()
        raw_delivery = (request.POST.get("buyer_delivery_cost") or "").strip()

        raw_status = (request.POST.get("status") or "").strip() or None

        cmd = UpdateOrder(
            order_id=order_id,

            date=timezone.datetime.fromisoformat(date_str).date() if date_str else None,
            notes=notes if notes != "" else None,

            business_unit_id=UUID(raw_bu) if raw_bu else None,
            buyer_id=UUID(raw_buyer) if raw_buyer else None,
            currency_id=(raw_currency.upper() if raw_currency else None),

            buyer_commission_percent=Decimal(raw_percent) if raw_percent else None,
            buyer_commission_amount=Decimal(raw_amount) if raw_amount else None,
            buyer_delivery_cost=Decimal(raw_delivery) if raw_delivery else None,

            status=raw_status,
        )

        service.update_order(cmd)
        return redirect("order_detail_page", order_id=order_id)

    return render(request, "orders/order_edit.html", {
        "order": obj,
        "business_units": business_units,
        "buyers": buyers,
        "currencies": currencies,
    })


def order_cancel_action(request, order_id):
    """
    Кнопка отмены — действие (POST), не страница.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    reason = (request.POST.get("reason") or "").strip() or None

    cmd = CancelOrder(order_id=order_id, reason=reason)
    service.cancel_order(cmd)

    return redirect("order_detail_page", order_id=order_id)


def order_events_page(request, order_id):
    """
    История событий заказа (читаем из EventStore таблицы Event).
    """
    order_obj = (
        OrderView.objects
        .filter(order_id=order_id)
        .select_related("business_unit", "buyer", "currency")
        .first()
    )

    events = (
        Event.objects
        .filter(aggregate_type=AGGREGATE_TYPE, aggregate_id=order_id)
        .order_by("aggregate_version")
    )

    return render(request, "orders/order_events.html", {
        "order": order_obj,
        "order_id": order_id,
        "events": events,
        "aggregate_type": AGGREGATE_TYPE,
    })