from uuid import UUID

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.application.order_service import OrderApplicationService
from orders.infrastructure.event_store import DjangoEventStore
from orders.projections.order_projector import OrderProjector  # <--- ВАЖНО: projections
from orders.domain.commands import CreateOrder, UpdateOrder, CancelOrder
from orders.models import Event, OrderView  # Event/OrderView экспортируются в orders/models/__init__.py

from .serializers import CreateOrderSerializer, UpdateOrderSerializer, CancelOrderSerializer


# Singleton wiring (простой вариант)
event_store = DjangoEventStore()
projector = OrderProjector()
service = OrderApplicationService(event_store=event_store, projector=projector, now_fn=timezone.now)


class CreateOrderView(APIView):
    """
    Команда создания заказа.
    """

    def post(self, request, order_id):
        ser = CreateOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        oid = order_id  # уже UUID из urls <uuid:order_id>

        cmd = CreateOrder(
            order_id=oid,
            human_code=ser.validated_data.get("human_code", "") or "",

            date=ser.validated_data["date"],
            business_unit_id=ser.validated_data["business_unit_id"],
            buyer_id=ser.validated_data["buyer_id"],

            # Currency PK = code (например "RUB"), поэтому это строка
            currency_id=ser.validated_data["currency_id"],

            notes=ser.validated_data.get("notes"),

            buyer_commission_percent=ser.validated_data.get("buyer_commission_percent"),
            buyer_commission_amount=ser.validated_data.get("buyer_commission_amount"),
            buyer_delivery_cost=ser.validated_data.get("buyer_delivery_cost", 0),
        )

        service.create_order(cmd)

        return Response(
            {"status": "ok", "order_id": str(oid)},
            status=status.HTTP_201_CREATED
        )


class UpdateOrderView(APIView):
    """
    Команда обновления шапки заказа.
    """

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
            currency_id=ser.validated_data.get("currency_id"),

            buyer_commission_percent=ser.validated_data.get("buyer_commission_percent"),
            buyer_commission_amount=ser.validated_data.get("buyer_commission_amount"),
            buyer_delivery_cost=ser.validated_data.get("buyer_delivery_cost"),

            status=(ser.validated_data.get("status") or None),
        )

        service.update_order(cmd)

        return Response({"status": "ok", "order_id": str(oid)}, status=status.HTTP_200_OK)


class CancelOrderView(APIView):
    """
    Команда отмены заказа.
    """

    def post(self, request, order_id):
        ser = CancelOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        oid = order_id

        cmd = CancelOrder(order_id=oid, reason=ser.validated_data.get("reason"))
        service.cancel_order(cmd)

        return Response({"status": "ok", "order_id": str(oid)}, status=status.HTTP_200_OK)


class OrderReadView(APIView):
    """
    Чтение из проекции OrderView.
    """

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

        return Response({
            "order_id": str(obj.order_id),
            "human_code": obj.human_code,
            "date": obj.date.isoformat(),
            "status": obj.status,

            "business_unit": {
                "id": str(obj.business_unit.id),
                "name": obj.business_unit.name,
                "short_code": obj.business_unit.short_code,
                "phone": obj.business_unit.phone,
                "address": obj.business_unit.address,
            },
            "buyer": {
                "id": str(obj.buyer.id),
                "name": obj.buyer.name,
                "short_code": obj.buyer.short_code,
                "phone": obj.buyer.phone,
                "address": obj.buyer.address,
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

            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
        })


class EventsList(APIView):
    """
    Отладочный эндпоинт: последние события.
    """

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