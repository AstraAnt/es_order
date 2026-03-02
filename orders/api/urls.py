from django.urls import path
from .views import CreateOrderView, UpdateOrderView, OrderReadView, EventsList, CancelOrderView

urlpatterns = [
    path("orders/<uuid:order_id>/commands/create", CreateOrderView.as_view()),
    path("orders/<uuid:order_id>/commands/update", UpdateOrderView.as_view()),
    path("orders/<uuid:order_id>/views/order", OrderReadView.as_view()),
    path("orders/<uuid:order_id>/commands/cancel", CancelOrderView.as_view()),
    path("events", EventsList.as_view()),
    ]

