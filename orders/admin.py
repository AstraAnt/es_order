from django.contrib import admin

from .models import (
    Event,
    ProjectorCheckpoint,
    OrderView,

    BusinessUnit,
    BusinessUnitMarketplaceToken,

    Partner,
    PartnerRole,

    UserBusinessUnitAccess,
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

    fields = (
        "marketplace",
        "token_name",
        "token_value",
        "is_active",
        "updated_at",
    )

    readonly_fields = ("updated_at",)
    show_change_link = False


@admin.register(BusinessUnitMarketplaceToken)
class BusinessUnitMarketplaceTokenAdmin(admin.ModelAdmin):
    list_display = (
        "business_unit",
        "marketplace",
        "token_name",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "marketplace",
        "is_active",
    )

    search_fields = (
        "business_unit__name",
        "business_unit__short_code",
        "token_name",
    )

    autocomplete_fields = ("business_unit",)


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "short_code", "is_active")
    search_fields = ("name", "short_code", "phone", "email")
    list_filter = ("is_active",)
    inlines = (BusinessUnitMarketplaceTokenInline,)


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
    list_display = (
        "human_code",
        "bu_code",
        "buyer_code",
        "status",
        "date",
        "currency",
        "items_total",
        "total_amount",
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

    autocomplete_fields = (
        "business_unit",
        "buyer",
    )

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


admin.site.register(ProjectorCheckpoint)
