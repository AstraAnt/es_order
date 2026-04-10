import uuid
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models import Sum
from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from finance.models import Currency
from orders.application.order_service import OrderApplicationService
from orders.domain.commands import (
    AddOrderItem,
    CancelOrder,
    CreateOrder,
    RemoveOrderItem,
    ResolveOrderItemToBarcode,
    SetOrderItemPrice,
    SetOrderItemQuantity,
    UpdateOrder,
)
from orders.domain.order import DomainError
from orders.infrastructure.event_store import DjangoEventStore
from orders.models import (
    BusinessUnit,
    BusinessUnitMarketplaceToken,
    Event,
    OrderItemView,
    OrderView,
    Partner,
    PlannedProduct,
    Product,
    ProductPhoto,
    ProductLink,
    ProductSKU,
    WBSyncRun,
)
from orders.projections.order_projector import OrderProjector
from orders.session import get_active_business_unit
from orders.services.wb_sync_service import sync_wb_catalog

AGGREGATE_TYPE = "PurchaseOrder"

event_store = DjangoEventStore()
projector = OrderProjector()
service = OrderApplicationService(event_store=event_store, projector=projector, now_fn=timezone.now)


def _catalog_context():
    return {
        "business_units": BusinessUnit.objects.filter(is_active=True).order_by("name"),
        "buyers": (
            Partner.objects
            .filter(is_active=True, roles__code="buyer")
            .distinct()
            .order_by("name")
        ),
        "currencies": Currency.objects.filter(is_active=True).order_by("code"),
        "planned_products": PlannedProduct.objects.filter(linked_product__isnull=True).order_by("name"),
        "real_products": (
            Product.objects
            .select_related("brand", "category")
            .order_by("seller_sku", "wb_sku")
        ),
    }


def _default_new_item_rows():
    return [{
        "kind": "real",
        "planned_product_id": "",
        "product_barcode": "",
        "quantity": "",
        "price": "",
    }]


def _normalize_decimal(raw_value, field_label, default=None, allow_blank=False):
    raw_value = (raw_value or "").strip()
    if raw_value == "":
        if allow_blank:
            return default
        raise ValidationError({field_label: f"Поле '{field_label}' обязательно."})
    try:
        return Decimal(raw_value)
    except Exception as exc:
        raise ValidationError({field_label: f"Поле '{field_label}' должно быть числом."}) from exc


def _humanize_field_error_key(field_key):
    if field_key.startswith("quantity_"):
        row_num = field_key.split("_")[-1]
        return f"Строка товара {row_num}: количество"
    if field_key.startswith("price_"):
        row_num = field_key.split("_")[-1]
        return f"Строка товара {row_num}: цена"
    if field_key.startswith("existing_quantity_"):
        row_num = field_key.split("_")[-1]
        return f"Текущая позиция {row_num}"
    if field_key.startswith("existing_price_"):
        row_num = field_key.split("_")[-1]
        return f"Текущая позиция {row_num}"
    if field_key.startswith("item_"):
        row_num = field_key.split("_")[-1]
        return f"Строка товара {row_num}: товар"
    if field_key == "items":
        return "Товары в заказе"
    return field_key


def _extract_new_item_rows(request):
    kinds = request.POST.getlist("new_item_kind")
    planned_ids = request.POST.getlist("new_planned_product_id")
    barcodes = request.POST.getlist("new_product_barcode")
    quantities = request.POST.getlist("new_quantity")
    prices = request.POST.getlist("new_price")

    rows_count = max(len(kinds), len(planned_ids), len(barcodes), len(quantities), len(prices), 1)
    rows = []
    for idx in range(rows_count):
        row = {
            "kind": (kinds[idx] if idx < len(kinds) else "real") or "real",
            "planned_product_id": (planned_ids[idx] if idx < len(planned_ids) else "").strip(),
            "product_barcode": (barcodes[idx] if idx < len(barcodes) else "").strip(),
            "quantity": (quantities[idx] if idx < len(quantities) else "").strip(),
            "price": (prices[idx] if idx < len(prices) else "").strip(),
        }
        if not any([
            row["planned_product_id"],
            row["product_barcode"],
            row["quantity"],
            row["price"],
        ]):
            continue
        rows.append(row)
    return rows


def _validate_new_item_rows(item_rows):
    if not item_rows:
        raise ValidationError({"items": "Добавьте хотя бы один товар в заказ."})

    planned_ids = {row["planned_product_id"] for row in item_rows if row["planned_product_id"]}
    product_refs = {row["product_barcode"] for row in item_rows if row["product_barcode"]}

    planned_map = {str(item.id): item for item in PlannedProduct.objects.filter(id__in=planned_ids)}
    product_map = {item.wb_sku: item for item in Product.objects.filter(wb_sku__in=product_refs)}
    sku_map = {item.barcode: item for item in ProductSKU.objects.select_related("product").filter(barcode__in=product_refs)}

    validated = []
    for index, row in enumerate(item_rows, start=1):
        quantity = _normalize_decimal(row["quantity"], f"quantity_{index}")
        price = _normalize_decimal(row["price"], f"price_{index}", default=Decimal("0"), allow_blank=True)
        if quantity <= 0:
            raise ValidationError({f"quantity_{index}": "Количество должно быть больше нуля."})
        if price < 0:
            raise ValidationError({f"price_{index}": "Цена не может быть отрицательной."})

        if row["kind"] == "planned":
            planned_product_id = row["planned_product_id"]
            if not planned_product_id:
                raise ValidationError({f"item_{index}": "Выберите плановый товар."})
            planned_product = planned_map.get(planned_product_id)
            if planned_product is None:
                raise ValidationError({f"item_{index}": "Плановый товар не найден."})
            validated.append({
                "planned_product_id": planned_product.id,
                "product_barcode": None,
                "quantity": quantity,
                "price": price,
            })
        else:
            product_ref = row["product_barcode"]
            if not product_ref:
                raise ValidationError({f"item_{index}": "Выберите реальный товар."})
            product = product_map.get(product_ref)
            if product is not None:
                resolved_value = product.wb_sku
            else:
                sku = sku_map.get(product_ref)
                resolved_value = sku.product.wb_sku if sku is not None else None
            if resolved_value is None:
                raise ValidationError({f"item_{index}": "Реальный товар не найден."})
            validated.append({
                "planned_product_id": None,
                "product_barcode": resolved_value,
                "quantity": quantity,
                "price": price,
            })

    return validated


def _decorate_order_items(items):
    items = list(items)
    planned_map = {
        str(item.id): item
        for item in PlannedProduct.objects.filter(
            id__in=[item.planned_product_id for item in items if item.planned_product_id]
        )
    }
    product_refs = [item.product_barcode for item in items if item.product_barcode]
    product_map = {
        item.wb_sku: item
        for item in Product.objects.select_related("brand", "category").filter(
            wb_sku__in=product_refs
        )
    }
    sku_map = {
        item.barcode: item
        for item in ProductSKU.objects.select_related("product").filter(
            barcode__in=product_refs
        )
    }

    decorated = []
    for item in items:
        planned = planned_map.get(str(item.planned_product_id)) if item.planned_product_id else None
        product = product_map.get(item.product_barcode) if item.product_barcode else None
        sku = sku_map.get(item.product_barcode) if item.product_barcode else None
        if planned is not None:
            label = f"Плановый товар: {planned.name}"
            kind = "planned"
            link = reverse("planned_product_edit_page", args=[planned.id])
        elif product is not None:
            label = f"WB SKU: {product.seller_sku} / {product.wb_sku}"
            kind = "real"
            link = f"{reverse('products_catalog_page')}?q={product.wb_sku}"
        elif sku is not None:
            label = f"WB SKU: {sku.product.seller_sku} / {sku.product.wb_sku}"
            kind = "real"
            link = f"{reverse('products_catalog_page')}?q={sku.product.wb_sku}"
        else:
            label = item.product_barcode or str(item.planned_product_id)
            kind = "unknown"
            link = None
        decorated.append({
            "item_id": item.item_id,
            "item_kind": kind,
            "item_label": label,
            "item_link": link,
            "quantity": item.quantity,
            "price": item.price,
            "subtotal": item.subtotal,
        })
    return decorated


def _form_error_message(exc):
    if hasattr(exc, "message_dict"):
        chunks = []
        for key, value in exc.message_dict.items():
            values = value if isinstance(value, list) else [str(value)]
            if key.startswith("existing_quantity_"):
                row_num = key.split("_")[-1]
                chunks.append(f"В текущей позиции {row_num} заполните количество.")
                continue
            if key.startswith("existing_price_"):
                row_num = key.split("_")[-1]
                chunks.append(f"В текущей позиции {row_num} укажите цену или оставьте 0.")
                continue
            chunks.append(f"{_humanize_field_error_key(key)}: {', '.join(values)}")
        return "; ".join(chunks)
    if hasattr(exc, "messages"):
        return "; ".join(exc.messages)
    return str(exc)


def _decorate_existing_items_for_form(items, request_post=None):
    decorated = _decorate_order_items(items)
    if request_post is None:
        return decorated

    existing_quantities = request_post.getlist("existing_quantity")
    existing_prices = request_post.getlist("existing_price")
    existing_remove = set(request_post.getlist("existing_remove"))

    for index, item in enumerate(decorated):
        if index < len(existing_quantities):
            item["quantity"] = existing_quantities[index]
        if index < len(existing_prices):
            item["price"] = existing_prices[index]
        item["marked_for_remove"] = str(item["item_id"]) in existing_remove

    return decorated


def _base_form_context(extra=None):
    context = _catalog_context()
    context.update({
        "today": timezone.now().date().isoformat(),
        "new_item_rows": _default_new_item_rows(),
        "form_error": None,
        "form_data": {},
    })
    if extra:
        context.update(extra)
    return context


def home_page(request):
    recent_orders = (
        OrderView.objects
        .select_related("business_unit", "buyer", "currency")
        .order_by("-updated_at")[:5]
    )
    total_amount = OrderView.objects.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
    context = {
        "orders_total": OrderView.objects.count(),
        "active_orders": OrderView.objects.filter(status="Active").count(),
        "cancelled_orders": OrderView.objects.filter(status="Cancelled").count(),
        "business_units_total": BusinessUnit.objects.filter(is_active=True).count(),
        "buyers_total": (
            Partner.objects
            .filter(is_active=True, roles__code="buyer")
            .distinct()
            .count()
        ),
        "total_amount": total_amount,
        "recent_orders": recent_orders,
        "active_business_unit": get_active_business_unit(request),
    }
    return render(request, "orders/home.html", context)


def orders_list_page(request):
    qs = (
        OrderView.objects
        .all()
        .select_related("business_unit", "buyer", "currency")
        .order_by("-updated_at")
    )
    return render(request, "orders/orders_list.html", {"orders": qs})


def order_detail_page(request, order_id):
    obj = get_object_or_404(
        OrderView.objects.select_related("business_unit", "buyer", "currency"),
        order_id=order_id
    )
    items = (
        OrderItemView.objects
        .filter(order_id=order_id, is_removed=False)
        .order_by("updated_at", "item_id")
    )
    return render(request, "orders/order_detail.html", {
        "order": obj,
        "items": _decorate_order_items(items),
    })


def order_create_page(request):
    active_business_unit = get_active_business_unit(request)

    if request.method == "POST":
        context = _base_form_context({
            "form_data": request.POST,
            "new_item_rows": _extract_new_item_rows(request) or _default_new_item_rows(),
            "active_business_unit": active_business_unit,
        })

        try:
            if active_business_unit is None:
                raise ValidationError({"business_unit": "Сначала выберите Business Unit в верхней панели."})

            order_id = uuid.uuid4()
            human_code = (request.POST.get("human_code") or "").strip()
            date_str = request.POST["date"]
            buyer_id = UUID(request.POST["buyer_id"])
            currency_code = (request.POST["currency_code"] or "").strip().upper()
            notes = (request.POST.get("notes") or "").strip() or None

            raw_percent = (request.POST.get("buyer_commission_percent") or "").strip()
            raw_amount = (request.POST.get("buyer_commission_amount") or "").strip()
            raw_delivery = (request.POST.get("buyer_delivery_cost") or "").strip()

            buyer_commission_percent = Decimal(raw_percent) if raw_percent else None
            buyer_commission_amount = Decimal(raw_amount) if raw_amount else None
            buyer_delivery_cost = Decimal(raw_delivery) if raw_delivery else Decimal("0")

            item_rows = _validate_new_item_rows(context["new_item_rows"])
            cmd = CreateOrder(
                order_id=order_id,
                human_code=human_code,
                date=timezone.datetime.fromisoformat(date_str).date(),
                business_unit_id=active_business_unit.id,
                buyer_id=buyer_id,
                currency_id=currency_code,
                notes=notes,
                buyer_commission_percent=buyer_commission_percent,
                buyer_commission_amount=buyer_commission_amount,
                buyer_delivery_cost=buyer_delivery_cost,
            )
            service.create_order(cmd)

            for row in item_rows:
                service.add_item(AddOrderItem(
                    order_id=order_id,
                    item_id=uuid.uuid4(),
                    product_barcode=row["product_barcode"],
                    planned_product_id=row["planned_product_id"],
                    quantity=row["quantity"],
                    price=row["price"],
                ))
            return redirect("order_detail_page", order_id=order_id)
        except (ValidationError, DomainError, ValueError) as exc:
            context["form_error"] = _form_error_message(exc)
            return render(request, "orders/order_create.html", context, status=400)

    return render(request, "orders/order_create.html", _base_form_context({
        "active_business_unit": active_business_unit,
    }))


def order_edit_page(request, order_id):
    obj = get_object_or_404(
        OrderView.objects.select_related("business_unit", "buyer", "currency"),
        order_id=order_id
    )
    current_items = (
        OrderItemView.objects
        .filter(order_id=order_id, is_removed=False)
        .order_by("updated_at", "item_id")
    )

    if request.method == "POST":
        new_item_rows = _extract_new_item_rows(request)
        context = _base_form_context({
            "order": obj,
            "existing_items": _decorate_existing_items_for_form(current_items, request.POST),
            "new_item_rows": new_item_rows or _default_new_item_rows(),
            "form_data": request.POST,
        })
        try:
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

            existing_quantities = request.POST.getlist("existing_quantity")
            existing_prices = request.POST.getlist("existing_price")
            existing_remove = set(request.POST.getlist("existing_remove"))
            for index, item in enumerate(list(current_items)):
                quantity_raw = existing_quantities[index] if index < len(existing_quantities) else str(item.quantity)
                price_raw = existing_prices[index] if index < len(existing_prices) else str(item.price)
                new_quantity = _normalize_decimal(quantity_raw, f"existing_quantity_{index + 1}")
                new_price = _normalize_decimal(
                    price_raw,
                    f"existing_price_{index + 1}",
                    default=Decimal("0"),
                    allow_blank=True,
                )

                if str(item.item_id) in existing_remove:
                    service.remove_item(RemoveOrderItem(order_id=order_id, item_id=item.item_id))
                    continue
                if new_quantity != item.quantity:
                    service.set_item_qty(SetOrderItemQuantity(
                        order_id=order_id,
                        item_id=item.item_id,
                        quantity=new_quantity,
                    ))
                if new_price != item.price:
                    service.set_item_price(SetOrderItemPrice(
                        order_id=order_id,
                        item_id=item.item_id,
                        price=new_price,
                    ))

            if new_item_rows:
                for row in _validate_new_item_rows(new_item_rows):
                    service.add_item(AddOrderItem(
                        order_id=order_id,
                        item_id=uuid.uuid4(),
                        product_barcode=row["product_barcode"],
                        planned_product_id=row["planned_product_id"],
                        quantity=row["quantity"],
                        price=row["price"],
                    ))
            messages.success(request, "Заказ обновлён. Текущие позиции сохранены.")
            return redirect("order_edit_page", order_id=order_id)
        except (ValidationError, DomainError, ValueError) as exc:
            context["form_error"] = _form_error_message(exc)
            return render(request, "orders/order_edit.html", context, status=400)

    return render(request, "orders/order_edit.html", _base_form_context({
        "order": obj,
        "existing_items": _decorate_existing_items_for_form(current_items),
    }))


def order_cancel_action(request, order_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    reason = (request.POST.get("reason") or "").strip() or None
    cmd = CancelOrder(order_id=order_id, reason=reason)
    service.cancel_order(cmd)
    return redirect("order_detail_page", order_id=order_id)


def order_events_page(request, order_id):
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


def product_matching_page(request):
    planned_products = (
        PlannedProduct.objects
        .select_related("linked_product")
        .order_by("-created_at", "name")
    )
    real_products_queryset = (
        Product.objects
        .select_related("brand", "category", "partner")
        .prefetch_related("skus", "photos")
        .order_by("seller_sku", "wb_sku")
    )
    real_products = []
    for product in real_products_queryset:
        barcodes = [sku.barcode for sku in product.skus.all()]
        product_photos = list(product.photos.all())
        primary_photo = next((photo for photo in product_photos if photo.local_path), product_photos[0] if product_photos else None)
        real_products.append({
            "product": product,
            "barcodes": barcodes,
            "preview_local_path": primary_photo.local_path if primary_photo and primary_photo.local_path else "",
            "preview_url": primary_photo.url if primary_photo else "",
            "option_label": (
                f"{product.seller_sku} · WB {product.wb_sku} · "
                f"{product.brand_id} / {product.category_id}"
                + (f" · barcodes: {', '.join(barcodes[:3])}" if barcodes else "")
            ),
            "search_text": " ".join([
                product.seller_sku,
                product.wb_sku,
                product.brand_id or "",
                product.category_id or "",
                " ".join(barcodes),
            ]).lower(),
        })

    page_message = None
    page_error = None

    if request.method == "POST":
        try:
            planned_product = get_object_or_404(
                PlannedProduct.objects.select_related("linked_product"),
                id=request.POST["planned_product_id"],
            )
            raw_product_id = (request.POST.get("product_wb_sku") or "").strip()
            if raw_product_id:
                product = get_object_or_404(Product, wb_sku=raw_product_id)
                planned_product.linked_product = product
                planned_product.save(update_fields=["linked_product"])
                product_link, _ = ProductLink.objects.update_or_create(
                    plan_product=planned_product,
                    defaults={
                        "product": product,
                        "linked_by": request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                    },
                )
                affected_items = list(
                    OrderItemView.objects
                    .filter(planned_product_id=planned_product.id, is_removed=False)
                    .order_by("updated_at", "item_id")
                )
                for item in affected_items:
                    service.resolve_item_to_barcode(ResolveOrderItemToBarcode(
                        order_id=item.order_id,
                        item_id=item.item_id,
                        to_product_barcode=product.wb_sku,
                        from_planned_product_id=planned_product.id,
                        link_id=product_link.id,
                    ))
                page_message = f"Сопоставление сохранено: «{planned_product.name}» -> «{product.seller_sku}»."
            else:
                planned_product.linked_product = None
                planned_product.save(update_fields=["linked_product"])
                ProductLink.objects.filter(plan_product=planned_product).delete()
                page_message = f"Связь для «{planned_product.name}» снята."
        except Exception as exc:
            page_error = _form_error_message(exc)

        planned_products = (
            PlannedProduct.objects
            .select_related("linked_product")
            .order_by("-created_at", "name")
        )

    return render(request, "orders/product_matching.html", {
        "planned_products": planned_products,
        "real_products": real_products,
        "matching_message": page_message,
        "matching_error": page_error,
    })


def planned_products_page(request):
    query = (request.GET.get("q") or "").strip()
    planned_products = PlannedProduct.objects.select_related("linked_product").order_by("-created_at", "name")
    if query:
        planned_products = planned_products.filter(
            Q(name__icontains=query) | Q(linked_product__seller_sku__icontains=query)
        )

    return render(request, "orders/planned_products_list.html", {
        "planned_products": planned_products,
        "planned_products_query": query,
    })


def planned_product_create_page(request):
    page_error = None
    form_data = {}

    if request.method == "POST":
        form_data = request.POST
        name = (request.POST.get("name") or "").strip()
        image = request.FILES.get("image")

        try:
            if not name:
                raise ValidationError({"name": "Укажите название планового товара."})

            planned_product = PlannedProduct.objects.create(
                name=name,
                image=image if image else None,
            )
            messages.success(request, f"Плановый товар «{planned_product.name}» создан.")
            return redirect("planned_product_edit_page", planned_product_id=planned_product.id)
        except ValidationError as exc:
            page_error = _form_error_message(exc)

    return render(request, "orders/planned_product_form.html", {
        "page_mode": "create",
        "page_title": "Создание планового товара",
        "page_kicker": "Каталог / плановые товары / создание",
        "submit_label": "Создать плановый товар",
        "form_error": page_error,
        "form_data": form_data,
        "planned_product": None,
    })


def planned_product_edit_page(request, planned_product_id):
    planned_product = get_object_or_404(
        PlannedProduct.objects.select_related("linked_product"),
        id=planned_product_id,
    )
    page_error = None
    form_data = {"name": planned_product.name}

    if request.method == "POST":
        form_data = request.POST
        name = (request.POST.get("name") or "").strip()
        image = request.FILES.get("image")
        remove_image = request.POST.get("remove_image") == "on"

        try:
            if not name:
                raise ValidationError({"name": "Укажите название планового товара."})

            planned_product.name = name
            if remove_image and planned_product.image:
                planned_product.image.delete(save=False)
                planned_product.image = None
            if image:
                if planned_product.image:
                    planned_product.image.delete(save=False)
                planned_product.image = image
            planned_product.save()

            messages.success(request, f"Плановый товар «{planned_product.name}» обновлён.")
            return redirect("planned_product_edit_page", planned_product_id=planned_product.id)
        except ValidationError as exc:
            page_error = _form_error_message(exc)

    return render(request, "orders/planned_product_form.html", {
        "page_mode": "edit",
        "page_title": "Корректировка планового товара",
        "page_kicker": "Каталог / плановые товары / корректировка",
        "submit_label": "Сохранить изменения",
        "form_error": page_error,
        "form_data": form_data,
        "planned_product": planned_product,
    })


def products_catalog_page(request):
    active_business_unit = get_active_business_unit(request)
    query = (request.GET.get("q") or "").strip()

    products = (
        Product.objects
        .select_related("brand", "category", "business_unit")
        .prefetch_related("skus", "photos")
        .order_by("seller_sku", "wb_sku")
    )
    if active_business_unit:
        products = products.filter(business_unit=active_business_unit)
    if query:
        products = products.filter(
            Q(seller_sku__icontains=query)
            | Q(wb_sku__icontains=query)
            | Q(skus__barcode__icontains=query)
        ).distinct()

    product_cards = []
    for product in products[:200]:
        skus = list(product.skus.all())
        photos = list(product.photos.all())
        product_cards.append({
            "product": product,
            "sku_count": len(skus),
            "photo_count": len(photos),
            "primary_photo": next((photo for photo in photos if photo.local_path), photos[0] if photos else None),
            "barcodes_preview": [sku.barcode for sku in skus[:3]],
        })

    latest_runs = (
        WBSyncRun.objects
        .select_related("business_unit", "triggered_by")
        .filter(business_unit=active_business_unit)[:6]
        if active_business_unit
        else WBSyncRun.objects.select_related("business_unit", "triggered_by")[:6]
    )

    return render(request, "orders/products_catalog.html", {
        "active_business_unit": active_business_unit,
        "catalog_query": query,
        "product_cards": product_cards,
        "products_total": products.count(),
        "latest_sync_runs": latest_runs,
    })


def wb_sync_page(request):
    active_business_unit = get_active_business_unit(request)
    page_message = None
    page_error = None
    selected_run_id = (request.GET.get("run_id") or "").strip()
    token_name_value = "default"

    if active_business_unit is not None:
        preferred_token = (
            BusinessUnitMarketplaceToken.objects
            .filter(
                business_unit=active_business_unit,
                marketplace=BusinessUnitMarketplaceToken.Marketplace.WILDBERRIES,
                is_active=True,
            )
            .order_by("-updated_at")
            .first()
        )
        if preferred_token:
            token_name_value = preferred_token.token_name

    if request.method == "POST":
        if active_business_unit is None:
            page_error = "Сначала выберите Business Unit в верхней панели."
        else:
            token_name = (request.POST.get("token_name") or token_name_value).strip() or token_name_value
            token_name_value = token_name
            raw_max_pages = (request.POST.get("max_pages") or "").strip()
            max_pages = int(raw_max_pages) if raw_max_pages else None
            should_download_photos = request.POST.get("download_photos", "on") == "on"
            overwrite_photos = request.POST.get("overwrite_photos") == "on"
            try:
                sync_run = sync_wb_catalog(
                    business_unit=active_business_unit,
                    token_name=token_name,
                    max_pages=max_pages,
                    download_photos=should_download_photos,
                    overwrite_photos=overwrite_photos,
                    triggered_by=getattr(request, "user", None),
                    trigger_source=WBSyncRun.TriggerSource.WEB,
                )
                selected_run_id = str(sync_run.id)
                page_message = (
                    f"Синк завершён: карточек {sync_run.cards_total}, "
                    f"ошибок по карточкам {sync_run.failed_cards}, ошибок по фото {sync_run.photos_failed}."
                )
            except Exception as exc:
                page_error = str(exc)

    runs_queryset = (
        WBSyncRun.objects
        .select_related("business_unit", "triggered_by")
        .filter(business_unit=active_business_unit)
        .order_by("-started_at")
        if active_business_unit
        else WBSyncRun.objects.none()
    )
    recent_runs = runs_queryset[:12]
    selected_run = None
    if selected_run_id:
        selected_run = runs_queryset.filter(id=selected_run_id).first()
    if selected_run is None:
        selected_run = runs_queryset.first()

    selected_logs = selected_run.logs.order_by("-created_at")[:120] if selected_run else []
    imported_products_count = (
        Product.objects.filter(business_unit=active_business_unit).count()
        if active_business_unit else 0
    )
    photos_count = (
        ProductPhoto.objects.filter(product__business_unit=active_business_unit).count()
        if active_business_unit else 0
    )

    return render(request, "orders/wb_sync.html", {
        "active_business_unit": active_business_unit,
        "sync_message": page_message,
        "sync_error": page_error,
        "token_name_value": token_name_value,
        "recent_runs": recent_runs,
        "selected_run": selected_run,
        "selected_logs": selected_logs,
        "imported_products_count": imported_products_count,
        "photos_count": photos_count,
    })


def wb_sync_now_action(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    active_business_unit = get_active_business_unit(request)
    if active_business_unit is None:
        messages.error(request, "Сначала выберите Business Unit в верхней панели.")
        return redirect("wb_sync_page")

    preferred_token = (
        BusinessUnitMarketplaceToken.objects
        .filter(
            business_unit=active_business_unit,
            marketplace=BusinessUnitMarketplaceToken.Marketplace.WILDBERRIES,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )
    token_name = preferred_token.token_name if preferred_token else "default"

    try:
        sync_run = sync_wb_catalog(
            business_unit=active_business_unit,
            token_name=token_name,
            download_photos=True,
            overwrite_photos=False,
            triggered_by=getattr(request, "user", None),
            trigger_source=WBSyncRun.TriggerSource.WEB,
        )
        messages.success(
            request,
            f"WB синк завершён: карточек {sync_run.cards_total}, новых товаров {sync_run.new_products}, "
            f"скачано фото {sync_run.photos_downloaded}, ошибок по фото {sync_run.photos_failed}.",
        )
        return redirect(f"{reverse('wb_sync_page')}?run_id={sync_run.id}")
    except Exception as exc:
        messages.error(request, f"WB синк завершился ошибкой: {exc}")
        return redirect("wb_sync_page")
