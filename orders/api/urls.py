from django.urls import path

from .views import (
    AddOrderItemView,
    CancelOrderView,
    CreateOrderView,
    EventsList,
    OrderReadView,
    RemoveOrderItemView,
    ResolveOrderItemToBarcodeView,
    SetOrderItemFxPlannedView,
    SetOrderItemPriceView,
    SetOrderItemQuantityView,
    UpdateOrderView,
)

urlpatterns = [
    # order
    path("orders/<uuid:order_id>/create/", CreateOrderView.as_view(), name="api_create_order"),
    path("orders/<uuid:order_id>/update/", UpdateOrderView.as_view(), name="api_update_order"),
    path("orders/<uuid:order_id>/cancel/", CancelOrderView.as_view(), name="api_cancel_order"),
    path("orders/<uuid:order_id>/", OrderReadView.as_view(), name="api_read_order"),

    # items
    path("orders/<uuid:order_id>/items/add/", AddOrderItemView.as_view(), name="api_add_order_item"),
    path("orders/<uuid:order_id>/items/<uuid:item_id>/remove/", RemoveOrderItemView.as_view(), name="api_remove_order_item"),
    path("orders/<uuid:order_id>/items/<uuid:item_id>/set-qty/", SetOrderItemQuantityView.as_view(), name="api_set_order_item_qty"),
    path("orders/<uuid:order_id>/items/<uuid:item_id>/set-price/", SetOrderItemPriceView.as_view(), name="api_set_order_item_price"),
    path("orders/<uuid:order_id>/items/<uuid:item_id>/set-fx-planned/", SetOrderItemFxPlannedView.as_view(), name="api_set_order_item_fx"),
    path("orders/<uuid:order_id>/items/<uuid:item_id>/resolve-to-barcode/", ResolveOrderItemToBarcodeView.as_view(), name="api_resolve_order_item_to_barcode"),

    # events
    path("events/", EventsList.as_view(), name="api_events_list"),
]
