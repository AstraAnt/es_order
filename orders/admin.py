from django.contrib import admin

from .models import Event, ProjectorCheckpoint, OrderView, Partner, PartnerRole, PartnerMarketplaceToken


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "aggregate_type", "aggregate_id", "aggregate_version", "event_type")
    list_filter = ("aggregate_type", "event_type")
    search_fields = ("aggregate_id", "event_type")


@admin.register(PartnerRole)
class PartnerRoleAdmin(admin.ModelAdmin):
    list_display = ("code", "title")
    search_fields = ("code", "title")


# Inline для токенов
class PartnerMarketplaceTokenInline(admin.TabularInline):
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
    list_display = ("name", "short_code", "get_roles", "is_active",)
    search_fields = ("name", "short_code", "phone", "email")
    list_filter = ("is_active", "roles")
    inlines = (PartnerMarketplaceTokenInline,)
    filter_horizontal = ("roles",)

    def get_roles(self, obj):
        return ", ".join(role.title for role in obj.roles.all())

    get_roles.short_description = "Roles"

admin.site.register(ProjectorCheckpoint)
admin.site.register(OrderView)
