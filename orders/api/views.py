from uuid import UUID, uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.application.order_service import OrderApplicationService
from orders.domain.commands import (
    AddOrderItem,
    CancelOrder,
    CreateOrder,
    RemoveOrderItem,
    ResolveOrderItemToBarcode,
    SetOrderItemFxPlanned,
    SetOrderItemPrice,
    SetOrderItemQuantity,
    UpdateOrder,
)
from orders.domain.order import DomainError
from orders.infrastructure.event_store import DjangoEventStore
from orders.models import Event, OrderItemView, OrderView
from orders.projections.order_projector import OrderProjector

from .serializers import (
    AddOrderItemSerializer,
    CancelOrderSerializer,
    CreateOrderSerializer,
    RemoveOrderItemSerializer,
    ResolveOrderItemToBarcodeSerializer,
    SetOrderItemFxPlannedSerializer,
    SetOrderItemPriceSerializer,
    SetOrderItemQuantitySerializer,
    UpdateOrderSerializer,
)


event_store = DjangoEventStore()
projector = OrderProjector()
service = OrderApplicationService(
    event_store=event_store,
    projector=projector,
    now_fn=timezone.now,
)


def _command_error_response(exc: Exception) -> Response:
    """
    Приводим доменные и validation ошибки к понятному API-ответу.
    """
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            return Response({"errors": exc.message_dict}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"errors": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, DomainError):
        return Response({"errors": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"errors": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)


# -------------------------
# ORDER
# -------------------------

class CreateOrderView(APIView):
    def post(self, request, order_id):
        ser = CreateOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        oid = order_id

        cmd = CreateOrder(
            order_id=oid,
            human_code=(ser.validated_data.get("human_code") or "").strip(),
            date=ser.validated_data["date"],
            business_unit_id=ser.validated_data["business_unit_id"],
            buyer_id=ser.validated_data["buyer_id"],
            currency_id=ser.validated_data["currency_id"].upper(),
            notes=ser.validated_data.get("notes"),
            buyer_commission_percent=ser.validated_data.get("buyer_commission_percent"),
            buyer_commission_amount=ser.validated_data.get("buyer_commission_amount"),
            buyer_delivery_cost=ser.validated_data.get("buyer_delivery_cost", 0),
        )

        try:
            service.create_order(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(oid)}, status=status.HTTP_201_CREATED)


class UpdateOrderView(APIView):
    def post(self, request, order_id):
        ser = UpdateOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        oid = order_id

        cmd = UpdateOrder(
            order_id=oid,
            date=ser.validated_data.get("date"),
            notes=ser.validated_data.get("notes"),
            business_unit_id=ser.validated_data.get("business_unit_id"),
            buyer_id=ser.validated_data.get("buyer_id"),
            currency_id=(
                ser.validated_data.get("currency_id").upper()
                if ser.validated_data.get("currency_id")
                else None
            ),
            buyer_commission_percent=ser.validated_data.get("buyer_commission_percent"),
            buyer_commission_amount=ser.validated_data.get("buyer_commission_amount"),
            buyer_delivery_cost=ser.validated_data.get("buyer_delivery_cost"),
            status=ser.validated_data.get("status") or None,
        )

        try:
            service.update_order(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(oid)})


class CancelOrderView(APIView):
    def post(self, request, order_id):
        ser = CancelOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        oid = order_id

        cmd = CancelOrder(
            order_id=oid,
            reason=ser.validated_data.get("reason"),
        )

        try:
            service.cancel_order(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(oid)})


class OrderReadView(APIView):
    def get(self, request, order_id):
        oid = order_id

        obj = (
            OrderView.objects
            .filter(order_id=oid)
            .select_related("business_unit", "buyer", "currency")
            .first()
        )
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        items = (
            OrderItemView.objects
            .filter(order_id=oid, is_removed=False)
            .order_by("updated_at", "item_id")
        )

        return Response({
            "order_id": str(obj.order_id),
            "human_code": obj.human_code,
            "date": obj.date.isoformat(),
            "status": obj.status,

            "business_unit": {
                "id": str(obj.business_unit.id),
                "name": obj.business_unit.name,
                "short_code": obj.business_unit.short_code,
            },
            "buyer": {
                "id": str(obj.buyer.id),
                "name": obj.buyer.name,
                "short_code": obj.buyer.short_code,
            },
            "currency": {
                "code": obj.currency.code,
                "name": obj.currency.name,
                "symbol": obj.currency.symbol,
            },

            "notes": obj.notes,
            "buyer_commission_percent": str(obj.buyer_commission_percent) if obj.buyer_commission_percent is not None else None,
            "buyer_commission_amount": str(obj.buyer_commission_amount) if obj.buyer_commission_amount is not None else None,
            "buyer_delivery_cost": str(obj.buyer_delivery_cost),

            "items_total": str(obj.items_total),
            "total_amount": str(obj.total_amount),

            "items": [
                {
                    "item_id": str(i.item_id),
                    "product_barcode": i.product_barcode,
                    "planned_product_id": str(i.planned_product_id) if i.planned_product_id else None,
                    "quantity": str(i.quantity),
                    "price": str(i.price),
                    "subtotal": str(i.subtotal),
                    "production_days": i.production_days,
                    "delivery_days": i.delivery_days,
                    "planned_fx_to_rub": str(i.planned_fx_to_rub) if i.planned_fx_to_rub is not None else None,
                    "notes": i.notes,
                }
                for i in items
            ],

            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
        })


# -------------------------
# ORDER ITEMS
# -------------------------

class AddOrderItemView(APIView):
    def post(self, request, order_id):
        ser = AddOrderItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        oid = order_id
        item_id = ser.validated_data.get("item_id") or uuid4()

        cmd = AddOrderItem(
            order_id=oid,
            item_id=item_id,
            product_barcode=(ser.validated_data.get("product_barcode") or None),
            planned_product_id=ser.validated_data.get("planned_product_id"),
            quantity=ser.validated_data["quantity"],
            price=ser.validated_data["price"],
            production_days=ser.validated_data.get("production_days", 0),
            delivery_days=ser.validated_data.get("delivery_days", 14),
            planned_fx_to_rub=ser.validated_data.get("planned_fx_to_rub"),
            notes=ser.validated_data.get("notes"),
        )

        try:
            service.add_item(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(oid), "item_id": str(item_id)}, status=status.HTTP_201_CREATED)


class RemoveOrderItemView(APIView):
    def post(self, request, order_id, item_id):
        ser = RemoveOrderItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        cmd = RemoveOrderItem(
            order_id=order_id,
            item_id=item_id,
            reason=ser.validated_data.get("reason"),
        )

        try:
            service.remove_item(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(order_id), "item_id": str(item_id)})


class SetOrderItemQuantityView(APIView):
    def post(self, request, order_id, item_id):
        ser = SetOrderItemQuantitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        cmd = SetOrderItemQuantity(
            order_id=order_id,
            item_id=item_id,
            quantity=ser.validated_data["quantity"],
        )

        try:
            service.set_item_qty(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(order_id), "item_id": str(item_id)})


class SetOrderItemPriceView(APIView):
    def post(self, request, order_id, item_id):
        ser = SetOrderItemPriceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        cmd = SetOrderItemPrice(
            order_id=order_id,
            item_id=item_id,
            price=ser.validated_data["price"],
        )

        try:
            service.set_item_price(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(order_id), "item_id": str(item_id)})


class SetOrderItemFxPlannedView(APIView):
    def post(self, request, order_id, item_id):
        ser = SetOrderItemFxPlannedSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        cmd = SetOrderItemFxPlanned(
            order_id=order_id,
            item_id=item_id,
            planned_fx_to_rub=ser.validated_data["planned_fx_to_rub"],
        )

        try:
            service.set_item_fx_planned(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(order_id), "item_id": str(item_id)})


class ResolveOrderItemToBarcodeView(APIView):
    def post(self, request, order_id, item_id):
        ser = ResolveOrderItemToBarcodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        cmd = ResolveOrderItemToBarcode(
            order_id=order_id,
            item_id=item_id,
            to_product_barcode=ser.validated_data["to_product_barcode"],
            from_planned_product_id=ser.validated_data.get("from_planned_product_id"),
            link_id=ser.validated_data.get("link_id"),
        )

        try:
            service.resolve_item_to_barcode(cmd)
        except Exception as exc:
            return _command_error_response(exc)

        return Response({"status": "ok", "order_id": str(order_id), "item_id": str(item_id)})


# -------------------------
# EVENTS
# -------------------------

class EventsList(APIView):
    def get(self, request):
        aggregate_id = request.query_params.get("aggregate_id")

        qs = Event.objects.all().order_by(
            "occurred_at", "aggregate_type", "aggregate_id", "aggregate_version"
        )

        if aggregate_id:
            qs = qs.filter(aggregate_id=UUID(aggregate_id))

        return Response([{
            "id": str(e.id),
            "aggregate_type": e.aggregate_type,
            "aggregate_id": str(e.aggregate_id),
            "aggregate_version": e.aggregate_version,
            "event_type": e.event_type,
            "occurred_at": e.occurred_at.isoformat(),
            "payload": e.payload,
            "metadata": e.metadata,
        } for e in qs[:500]])
