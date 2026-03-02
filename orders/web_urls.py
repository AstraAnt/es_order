from django.urls import path
from .web_views import (
    orders_list_page, order_detail_page, order_create_page,
    order_edit_page, order_cancel_action, order_events_page
)


urlpatterns = [
    path("orders/", orders_list_page, name="orders_list_page"),
    path("orders/create/", order_create_page, name="order_create_page"),
    path("orders/<uuid:order_id>/", order_detail_page, name="order_detail_page"),
    path("orders/<uuid:order_id>/edit/", order_edit_page, name="order_edit_page"),
    path("orders/<uuid:order_id>/cancel/", order_cancel_action, name="order_cancel_action"),
    path("orders/<uuid:order_id>/events/", order_events_page, name="order_events_page"),
]