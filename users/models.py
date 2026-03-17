from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.apps import apps


class Role(models.Model):
    """
    Роль пользователя внутри business unit.
    Например:
    - admin
    - manager
    - buyer
    - warehouse
    - viewer
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Код/название роли")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
        ordering = ("name",)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Пользователь сайта.

    Поле role оставлено временно для обратной совместимости,
    но для новых прав доступа по business unit используйте membership-модель ниже.
    """
    role = models.ForeignKey(
        "Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Глобальная роль"
    )

    def has_role(self, role_name: str) -> bool:
        return self.role and self.role.name == role_name

    def __str__(self):
        return self.username


class UserBusinessUnitMembership(models.Model):
    """
    Связь пользователя с business unit и ролью внутри него.

    ВАЖНО:
    В settings.py нужно добавить:
        BUSINESS_UNIT_MODEL = "your_app.BusinessUnit"

    Пример:
        BUSINESS_UNIT_MODEL = "partners.BusinessUnit"
    или
        BUSINESS_UNIT_MODEL = "core.BusinessUnit"
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_unit_memberships",
        verbose_name="Пользователь",
    )

    business_unit_app_label = None  # просто для читаемости

    business_unit_id = models.PositiveBigIntegerField(verbose_name="ID business unit")
    role = models.ForeignKey(
        "Role",
        on_delete=models.PROTECT,
        related_name="business_unit_memberships",
        verbose_name="Роль",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Доступ пользователя к business unit"
        verbose_name_plural = "Доступы пользователей к business unit"
        unique_together = ("user", "business_unit_id", "role")
        indexes = [
            models.Index(fields=("user", "business_unit_id", "is_active")),
        ]

    def __str__(self):
        return f"{self.user} / BU:{self.business_unit_id} / {self.role}"

    @property
    def business_unit(self):
        model_label = getattr(settings, "BUSINESS_UNIT_MODEL", None)
        if not model_label:
            return None

        model = apps.get_model(model_label)
        if model is None:
            return None

        try:
            return model.objects.get(pk=self.business_unit_id)
        except model.DoesNotExist:
            return None