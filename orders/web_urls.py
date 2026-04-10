from django.urls import path
from .views_business_unit import select_business_unit_page
from .web_views import (
    home_page,
    planned_product_create_page,
    planned_product_edit_page,
    planned_products_page,
    products_catalog_page,
    product_matching_page,
    wb_sync_now_action,
    wb_sync_page,
    orders_list_page, order_detail_page, order_create_page,
    order_edit_page, order_cancel_action, order_events_page
)


urlpatterns = [
    path("", home_page, name="home_page"),
    path("business-unit/select/", select_business_unit_page, name="select_business_unit_page"),
    path("products/planned/", planned_products_page, name="planned_products_page"),
    path("products/planned/create/", planned_product_create_page, name="planned_product_create_page"),
    path("products/planned/<int:planned_product_id>/edit/", planned_product_edit_page, name="planned_product_edit_page"),
    path("products/catalog/", products_catalog_page, name="products_catalog_page"),
    path("products/matching/", product_matching_page, name="product_matching_page"),
    path("products/wb-sync/", wb_sync_page, name="wb_sync_page"),
    path("products/wb-sync/run-now/", wb_sync_now_action, name="wb_sync_now_action"),
    path("orders/", orders_list_page, name="orders_list_page"),
    path("orders/create/", order_create_page, name="order_create_page"),
    path("orders/<uuid:order_id>/", order_detail_page, name="order_detail_page"),
    path("orders/<uuid:order_id>/edit/", order_edit_page, name="order_edit_page"),
    path("orders/<uuid:order_id>/cancel/", order_cancel_action, name="order_cancel_action"),
    path("orders/<uuid:order_id>/events/", order_events_page, name="order_events_page"),
]
