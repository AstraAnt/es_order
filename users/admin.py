from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Role, UserBusinessUnitMembership


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    search_fields = ("name",)


@admin.register(UserBusinessUnitMembership)
class UserBusinessUnitMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "business_unit_id", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("user__username", "user__email")


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Роли и доступы", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "role", "is_staff", "is_active")