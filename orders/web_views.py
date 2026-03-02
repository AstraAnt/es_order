import uuid
from decimal import Decimal
from uuid import UUID

from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from orders.domain.commands import CreateOrder, UpdateOrder, CancelOrder
from orders.models import OrderView, Event, Partner
from orders.projections.order_projector import project_order_event
from orders.projections.runner import ProjectorRunner
from orders.services.order_service import load_order, append_and_project


def orders_list_page(request):
    """
    Страница-список всех заказов из OrderView.
    Это read-model (проекция), т.е. читать быстро и удобно.
    """
    qs = OrderView.objects.all().select_related("supplier").order_by("-updated_at")
    return render(request, "orders/orders_list.html", {"orders": qs})


def order_detail_page(request, order_id):
    """
    Детальная страница одного заказа (проекция OrderView).
    order_id придёт как UUID, потому что в urls <uuid:order_id>.
    """
    obj = get_object_or_404(OrderView.objects.select_related("supplier"), order_id=order_id)
    return render(request, "orders/order_detail.html", {"order": obj})


runner = ProjectorRunner(
    projector_name="web_orders_projector",
    project_func=project_order_event
)


def order_create_page(request):
    """
    HTML страница создания заказа.
    Это UI над командой CreateOrder.

    Мы НЕ даём вводить поставщика руками — выбираем из справочника Partner с ролью Supplier.
    """
    suppliers = (
        Partner.objects
        .filter(is_active=True, roles__code=Partner.Role.SUPPLIER)
        .distinct()
        .order_by("name")
    )

    if request.method == "POST":
        order_id = uuid.uuid4()

        # Из формы приходит строка UUID -> превращаем в UUID объект для домена
        supplier_id = UUID(request.POST["supplier_id"])

        order_currency = request.POST["order_currency"]
        order_amount = Decimal(request.POST["order_amount"])
        base_currency = request.POST["base_currency"]

        order = load_order(order_id)

        events = order.handle_create(
            timezone.now(),
            CreateOrder(
                order_id=order_id,
                supplier_id=supplier_id,
                order_currency=order_currency,
                order_amount=order_amount,
                base_currency=base_currency,
            )
        )

        append_and_project(runner, order_id, order.state.version, events)

        return redirect("order_detail_page", order_id=order_id)

    return render(request, "orders/order_create.html", {"suppliers": suppliers})


def order_edit_page(request, order_id):
    """
    Форма изменения заказа (UI над командой UpdateOrder).
    """
    obj = get_object_or_404(OrderView.objects.select_related("supplier"), order_id=order_id)
    suppliers = (
        Partner.objects
        .filter(is_active=True, roles__code=Partner.Role.SUPPLIER)
        .distinct()
        .order_by("name")
    )

    if request.method == "POST":
        # supplier_id может прийти пустым (если пользователь не менял), тогда None
        raw_supplier_id = request.POST.get("supplier_id") or None
        supplier_id = UUID(raw_supplier_id) if raw_supplier_id else None

        order_currency = request.POST.get("order_currency") or None
        order_amount = request.POST.get("order_amount") or None
        status = request.POST.get("status") or None

        order = load_order(order_id)

        amt = Decimal(order_amount) if order_amount else None

        events = order.handle_update(
            timezone.now(),
            UpdateOrder(
                order_id=order_id,
                supplier_id=supplier_id,
                order_currency=order_currency,
                order_amount=amt,
                status=status,
            )
        )

        append_and_project(runner, order_id, order.state.version, events)
        return redirect("order_detail_page", order_id=order_id)

    return render(request, "orders/order_edit.html", {"order": obj, "suppliers": suppliers})


def order_cancel_action(request, order_id):
    """
    Кнопка отмены — это действие (POST), не страница.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    reason = request.POST.get("reason") or None

    order = load_order(order_id)
    events = order.handle_cancel(timezone.now(), CancelOrder(order_id=order_id, reason=reason))
    append_and_project(runner, order_id, order.state.version, events)

    return redirect("order_detail_page", order_id=order_id)


def order_events_page(request, order_id):
    """
    История событий = чтение из EventStore.
    """
    order_obj = OrderView.objects.filter(order_id=order_id).select_related("supplier").first()

    events = (
        Event.objects
        .filter(aggregate_type="Order", aggregate_id=order_id)
        .order_by("aggregate_version")
    )

    return render(request, "orders/order_events.html", {
        "order": order_obj,
        "order_id": order_id,
        "events": events,
    })
