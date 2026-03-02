from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Настройки отображения юзера в админке.
    """
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Роль", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "role")