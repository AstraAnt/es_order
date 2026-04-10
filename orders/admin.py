from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Brand,
    BusinessUnit,
    BusinessUnitMarketplaceToken,
    Category,
    Event,
    OrderItemView,
    OrderView,
    Partner,
    PartnerRole,
    Product,
    ProductPhoto,
    ProductSKU,
    ProjectorCheckpoint,
    UserBusinessUnitAccess,
    WBSyncLog,
    WBSyncRun,
)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "aggregate_type", "aggregate_id", "aggregate_version", "event_type")
    list_filter = ("aggregate_type", "event_type")
    search_fields = ("aggregate_id", "event_type")


@admin.register(PartnerRole)
class PartnerRoleAdmin(admin.ModelAdmin):
    list_display = ("code", "title")
    search_fields = ("code", "title")


class BusinessUnitMarketplaceTokenInline(admin.TabularInline):
    model = BusinessUnitMarketplaceToken
    extra = 0
    min_num = 0
    fields = ("marketplace", "token_name", "token_value", "is_active", "updated_at")
    readonly_fields = ("updated_at",)
    show_change_link = False


@admin.register(BusinessUnitMarketplaceToken)
class BusinessUnitMarketplaceTokenAdmin(admin.ModelAdmin):
    list_display = ("business_unit", "marketplace", "token_name", "is_active", "updated_at")
    list_filter = ("marketplace", "is_active")
    search_fields = ("business_unit__name", "business_unit__short_code", "token_name")
    autocomplete_fields = ("business_unit",)


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "short_code", "is_active", "wb_sync_link")
    search_fields = ("name", "short_code", "phone", "email")
    list_filter = ("is_active",)
    inlines = (BusinessUnitMarketplaceTokenInline,)

    def wb_sync_link(self, obj):
        return format_html('<a href="{}">Открыть WB синк</a>', reverse("wb_sync_page"))

    wb_sync_link.short_description = "WB Sync"


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "short_code", "get_roles", "is_active")
    search_fields = ("name", "short_code", "phone", "email")
    list_filter = ("is_active", "roles")
    filter_horizontal = ("roles",)

    def get_roles(self, obj):
        return ", ".join(role.title for role in obj.roles.all())

    get_roles.short_description = "Roles"


@admin.register(UserBusinessUnitAccess)
class UserBusinessUnitAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "business_unit", "is_active")
    list_filter = ("is_active", "business_unit")
    search_fields = ("user__username", "user__email", "business_unit__name", "business_unit__short_code")
    autocomplete_fields = ("user", "business_unit")


@admin.register(OrderView)
class OrderViewAdmin(admin.ModelAdmin):
    """
    Админка read-model заказа.

    ВАЖНО:
    - OrderItemView не имеет FK на OrderView
    - поэтому обычный Inline использовать нельзя
    - вместо этого даём ссылку "Items" на список строк заказа
    """
    list_display = (
        "human_code",
        "bu_code",
        "buyer_code",
        "status",
        "date",
        "currency",
        "items_total",
        "total_amount",
        "items_link",
        "updated_at",
    )
    list_display_links = ("human_code",)

    search_fields = (
        "human_code",
        "business_unit__name",
        "business_unit__short_code",
        "buyer__name",
        "buyer__short_code",
    )

    list_filter = (
        "status",
        "currency",
        "date",
        "business_unit",
        "buyer",
    )

    ordering = ("-updated_at",)
    autocomplete_fields = ("business_unit", "buyer")

    readonly_fields = (
        "order_id",
        "human_code",
        "business_unit",
        "buyer",
        "currency",
        "date",
        "notes",
        "buyer_commission_percent",
        "buyer_commission_amount",
        "buyer_delivery_cost",
        "items_total",
        "total_amount",
        "status",
        "created_at",
        "updated_at",
    )

    def bu_code(self, obj):
        return obj.business_unit.short_code if obj.business_unit else ""

    bu_code.short_description = "BU"
    bu_code.admin_order_field = "business_unit__short_code"

    def buyer_code(self, obj):
        return obj.buyer.short_code if obj.buyer else ""

    buyer_code.short_description = "Buyer"
    buyer_code.admin_order_field = "buyer__short_code"

    def items_link(self, obj):
        url = reverse("admin:orders_orderitemview_changelist")
        return format_html('<a href="{}?order_id={}">Строки</a>', url, obj.order_id)

    items_link.short_description = "Items"


@admin.register(OrderItemView)
class OrderItemViewAdmin(admin.ModelAdmin):
    """
    Отдельная админка строк заказа.
    """
    list_display = (
        "item_id",
        "order_link",
        "product_barcode",
        "planned_product_id",
        "quantity",
        "price",
        "subtotal_value",
        "is_removed",
        "updated_at",
    )

    list_filter = ("is_removed",)
    search_fields = ("item_id", "order_id", "product_barcode")
    ordering = ("-updated_at",)

    readonly_fields = (
        "item_id",
        "order_id",
        "product_barcode",
        "planned_product_id",
        "quantity",
        "price",
        "production_days",
        "delivery_days",
        "planned_fx_to_rub",
        "notes",
        "is_removed",
        "updated_at",
    )

    def subtotal_value(self, obj):
        return obj.subtotal

    subtotal_value.short_description = "Subtotal"

    def order_link(self, obj):
        try:
            ov = OrderView.objects.get(order_id=obj.order_id)
            url = reverse("admin:orders_orderview_change", args=[ov.order_id])
            return format_html('<a href="{}">{}</a>', url, ov.human_code)
        except OrderView.DoesNotExist:
            return str(obj.order_id)

    order_link.short_description = "Order"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        order_id = request.GET.get("order_id")
        if order_id:
            qs = qs.filter(order_id=order_id)
        return qs


admin.site.register(ProjectorCheckpoint)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("wb_sku", "seller_sku", "brand", "category", "business_unit")
    search_fields = ("wb_sku", "seller_sku")
    list_filter = ("business_unit", "brand", "category")
    autocomplete_fields = ("business_unit", "partner")


@admin.register(ProductSKU)
class ProductSKUAdmin(admin.ModelAdmin):
    list_display = ("barcode", "product", "tech_size", "wb_size", "color")
    search_fields = ("barcode", "product__seller_sku", "product__wb_sku")
    autocomplete_fields = ("product",)


@admin.register(ProductPhoto)
class ProductPhotoAdmin(admin.ModelAdmin):
    list_display = ("product", "photo_type", "url", "local_path")
    search_fields = ("product__seller_sku", "product__wb_sku", "url", "local_path")
    autocomplete_fields = ("product",)


@admin.register(WBSyncRun)
class WBSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "business_unit",
        "status",
        "cards_total",
        "failed_cards",
        "photos_downloaded",
        "photos_failed",
        "trigger_source",
    )
    list_filter = ("status", "trigger_source", "business_unit")
    search_fields = ("business_unit__name", "business_unit__short_code", "token_name", "error_message")
    readonly_fields = (
        "id",
        "business_unit",
        "triggered_by",
        "trigger_source",
        "token_name",
        "max_pages",
        "download_photos",
        "overwrite_photos",
        "status",
        "started_at",
        "completed_at",
        "error_message",
        "pages_total",
        "cards_total",
        "failed_cards",
        "new_products",
        "updated_products",
        "new_skus",
        "updated_skus",
        "new_photos",
        "updated_photos",
        "photos_total",
        "photos_downloaded",
        "photos_skipped",
        "photos_failed",
    )


@admin.register(WBSyncLog)
class WBSyncLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sync_run", "stage", "level", "entity_label", "entity_id")
    list_filter = ("stage", "level")
    search_fields = ("entity_id", "entity_label", "message", "sync_run__business_unit__short_code")
    autocomplete_fields = ("sync_run",)
