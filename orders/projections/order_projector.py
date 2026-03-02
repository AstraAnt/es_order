from __future__ import annotations

from decimal import Decimal
from typing import List
from uuid import UUID

from django.db import transaction

from orders.domain.events import (
    DomainEvent,
    ORDER_CREATED,
    ORDER_UPDATED,
    ORDER_CANCELLED,
    ORDER_ITEM_ADDED,
    ORDER_ITEM_REMOVED,
    ORDER_ITEM_QTY_SET,
    ORDER_ITEM_PRICE_SET,
    ORDER_ITEM_FX_PLANNED_SET,
    ORDER_ITEM_RESOLVED_TO_BARCODE,
)
from orders.models.order import OrderView, OrderItemView
from orders.models import Partner
from finance.models import Currency


class OrderProjector:
    """
    Проектор обновляет read-модели на основе доменных событий.

    Обновляем:
    - OrderView (шапка заказа)
    - OrderItemView (строки заказа)

    И пересчитываем totals в OrderView.
    """

    @transaction.atomic
    def project(self, domain_events: List[DomainEvent]) -> None:
        for e in domain_events:
            if e.event_type == ORDER_CREATED:
                self._on_created(e)
            elif e.event_type == ORDER_UPDATED:
                self._on_updated(e)
            elif e.event_type == ORDER_CANCELLED:
                self._on_cancelled(e)

            elif e.event_type == ORDER_ITEM_ADDED:
                self._on_item_added(e)
                self._recalc_totals(e.aggregate_id)

            elif e.event_type == ORDER_ITEM_REMOVED:
                self._on_item_removed(e)
                self._recalc_totals(e.aggregate_id)

            elif e.event_type == ORDER_ITEM_QTY_SET:
                self._on_item_qty_set(e)
                self._recalc_totals(e.aggregate_id)

            elif e.event_type == ORDER_ITEM_PRICE_SET:
                self._on_item_price_set(e)
                self._recalc_totals(e.aggregate_id)

            elif e.event_type == ORDER_ITEM_FX_PLANNED_SET:
                # FX не влияет на totals qty*price, но влияет на планы/отчеты (если нужно)
                self._on_item_fx_set(e)

            elif e.event_type == ORDER_ITEM_RESOLVED_TO_BARCODE:
                self._on_item_resolved_to_barcode(e)

    # ---------- ORDER VIEW ----------

    def _on_created(self, e: DomainEvent) -> None:
        p = e.payload
        ov = OrderView(
            order_id=e.aggregate_id,
            human_code=p["human_code"],

            business_unit=Partner.objects.get(id=p["business_unit_id"]),
            buyer=Partner.objects.get(id=p["buyer_id"]),
            currency=Currency.objects.get(id=p["currency_id"]),

            date=p["date"],
            notes=p.get("notes"),

            buyer_commission_percent=Decimal(p["buyer_commission_percent"]) if p.get("buyer_commission_percent") else None,
            buyer_commission_amount=Decimal(p["buyer_commission_amount"]) if p.get("buyer_commission_amount") else None,
            buyer_delivery_cost=Decimal(p.get("buyer_delivery_cost", "0")),

            status=p.get("status", "Active"),
            created_at=e.occurred_at,
        )
        ov.full_clean()
        ov.save()

    def _on_updated(self, e: DomainEvent) -> None:
        p = e.payload
        ov = OrderView.objects.select_for_update().get(order_id=e.aggregate_id)

        if "date" in p:
            ov.date = p["date"]
        if "notes" in p:
            ov.notes = p["notes"]

        if "business_unit_id" in p:
            ov.business_unit = Partner.objects.get(id=p["business_unit_id"])
        if "buyer_id" in p:
            ov.buyer = Partner.objects.get(id=p["buyer_id"])
        if "currency_id" in p:
            ov.currency = Currency.objects.get(id=p["currency_id"])

        if "buyer_commission_percent" in p:
            ov.buyer_commission_percent = Decimal(p["buyer_commission_percent"]) if p["buyer_commission_percent"] is not None else None
        if "buyer_commission_amount" in p:
            ov.buyer_commission_amount = Decimal(p["buyer_commission_amount"]) if p["buyer_commission_amount"] is not None else None
        if "buyer_delivery_cost" in p:
            ov.buyer_delivery_cost = Decimal(p["buyer_delivery_cost"])

        if "status" in p:
            ov.status = p["status"]

        ov.full_clean()
        ov.save()

        # Параметры комиссии могли измениться => totals могут измениться
        self._recalc_totals(e.aggregate_id)

    def _on_cancelled(self, e: DomainEvent) -> None:
        ov = OrderView.objects.select_for_update().get(order_id=e.aggregate_id)
        ov.status = "Cancelled"
        ov.save()

    # ---------- ITEMS VIEW (BARCODE) ----------

    def _on_item_added(self, e: DomainEvent) -> None:
        p = e.payload
        OrderItemView.objects.update_or_create(
            item_id=p["item_id"],
            defaults={
                "order_id": e.aggregate_id,

                # ключевое: barcode
                "product_barcode": p.get("product_barcode"),
                "planned_product_id": p.get("planned_product_id"),

                "quantity": Decimal(p["quantity"]),
                "price": Decimal(p["price"]),
                "production_days": int(p.get("production_days", 0)),
                "delivery_days": int(p.get("delivery_days", 14)),
                "planned_fx_to_rub": Decimal(p["planned_fx_to_rub"]) if p.get("planned_fx_to_rub") is not None else None,
                "notes": p.get("notes"),
                "is_removed": False,
            }
        )

    def _on_item_removed(self, e: DomainEvent) -> None:
        p = e.payload
        item = OrderItemView.objects.select_for_update().get(item_id=p["item_id"])
        item.is_removed = True
        item.save()

    def _on_item_qty_set(self, e: DomainEvent) -> None:
        p = e.payload
        item = OrderItemView.objects.select_for_update().get(item_id=p["item_id"])
        item.quantity = Decimal(p["quantity"])
        item.save()

    def _on_item_price_set(self, e: DomainEvent) -> None:
        p = e.payload
        item = OrderItemView.objects.select_for_update().get(item_id=p["item_id"])
        item.price = Decimal(p["price"])
        item.save()

    def _on_item_fx_set(self, e: DomainEvent) -> None:
        p = e.payload
        item = OrderItemView.objects.select_for_update().get(item_id=p["item_id"])
        item.planned_fx_to_rub = Decimal(p["planned_fx_to_rub"])
        item.save()

    def _on_item_resolved_to_barcode(self, e: DomainEvent) -> None:
        p = e.payload
        item = OrderItemView.objects.select_for_update().get(item_id=p["item_id"])
        item.product_barcode = p["to_product_barcode"]
        item.planned_product_id = None
        item.save()

    # ---------- TOTALS ----------

    def _recalc_totals(self, order_id: UUID) -> None:
        """
        Пересчёт totals заказа по строкам.

        items_total = SUM(qty*price) по строкам, где is_removed=False
        total_amount = items_total + комиссия + доставка

        Почему так:
        - В ES домен можно не нагружать расчётами для UI
        - Проекция удобна и быстра
        """
        ov = OrderView.objects.select_for_update().get(order_id=order_id)

        items = OrderItemView.objects.filter(order_id=order_id, is_removed=False)
        items_total = sum((i.subtotal for i in items), Decimal("0"))
        ov.items_total = items_total

        commission = Decimal("0")
        if ov.buyer_commission_amount is not None:
            commission = ov.buyer_commission_amount
        elif ov.buyer_commission_percent is not None:
            commission = (items_total * ov.buyer_commission_percent) / Decimal("100")

        ov.total_amount = items_total + commission + (ov.buyer_delivery_cost or Decimal("0"))
        ov.save()