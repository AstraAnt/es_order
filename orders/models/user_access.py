import uuid

from django.db import models


class UserBusinessUnitAccess(models.Model):
    """
    Доступ пользователя к Business Unit.

    Почему отдельная модель, а не ManyToMany прямо в users.User:
    - не надо лезть в модель пользователя
    - легче внедрить без слома существующей auth-архитектуры
    - можно хранить доп. метаданные (активность, приоритет, комментарий)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="business_unit_accesses",
    )

    business_unit = models.ForeignKey(
        "orders.BusinessUnit",
        on_delete=models.CASCADE,
        related_name="user_accesses",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "User Business Unit Access"
        verbose_name_plural = "User Business Unit Accesses"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "business_unit"],
                name="uniq_user_business_unit_access",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["business_unit", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user} -> {self.business_unit}"