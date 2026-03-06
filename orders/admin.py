from django.contrib import admin

from .models import (
    Event,
    ProjectorCheckpoint,
    OrderView,
    Partner,
    PartnerRole,
    PartnerMarketplaceToken,
)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Админка для EventStore.
    Удобна для отладки и просмотра потока событий.
    """
    list_display = ("occurred_at", "aggregate_type", "aggregate_id", "aggregate_version", "event_type")
    list_filter = ("aggregate_type", "event_type")
    search_fields = ("aggregate_id", "event_type")


@admin.register(PartnerRole)
class PartnerRoleAdmin(admin.ModelAdmin):
    """
    Справочник ролей партнёров.
    """
    list_display = ("code", "title")
    search_fields = ("code", "title")


class PartnerMarketplaceTokenInline(admin.TabularInline):
    """
    Вложенная таблица токенов маркетплейсов внутри карточки партнёра.
    """
    model = PartnerMarketplaceToken
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


@admin.register(PartnerMarketplaceToken)
class PartnerMarketplaceTokenAdmin(admin.ModelAdmin):
    """
    Отдельная админка токенов маркетплейсов.
    """
    list_display = (
        "partner",
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
        "partner__name",
        "token_name",
    )

    autocomplete_fields = ("partner",)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    """
    Админка партнёров.
    """
    list_display = ("name", "short_code", "get_roles", "is_active")
    search_fields = ("name", "short_code", "phone", "email")
    list_filter = ("is_active", "roles")
    inlines = (PartnerMarketplaceTokenInline,)
    filter_horizontal = ("roles",)

    def get_roles(self, obj):
        return ", ".join(role.title for role in obj.roles.all())

    get_roles.short_description = "Roles"


@admin.register(OrderView)
class OrderViewAdmin(admin.ModelAdmin):
    """
    Админка для read-model заказа.

    Что показываем:
    - human_code как главный читаемый номер заказа
    - короткие коды BU и Buyer отдельными колонками
    - статус, дату, валюту, суммы

    Поля делаем readonly, потому что OrderView — это проекция из событий,
    а не основной write-model. Менять её руками в админке не нужно.
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
        "updated_at",
    )

    # Клик по human_code открывает карточку объекта
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
        """
        Короткий код Business Unit.
        Полезно для компактного списка заказов.
        """
        if obj.business_unit:
            return obj.business_unit.short_code
        return ""

    bu_code.short_description = "BU"
    bu_code.admin_order_field = "business_unit__short_code"

    def buyer_code(self, obj):
        """
        Короткий код Buyer.
        """
        if obj.buyer:
            return obj.buyer.short_code
        return ""

    buyer_code.short_description = "Buyer"
    buyer_code.admin_order_field = "buyer__short_code"


admin.site.register(ProjectorCheckpoint)