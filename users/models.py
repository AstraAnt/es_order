from django.contrib.auth.models import AbstractUser
from django.db import models

class Role(models.Model):
    """
    Роль пользователя.
    Например:
    - admin (полный доступ)
    - manager (ведёт клиентов)
    - buyer (занимается закупками)
    - warehouse (склад)
    - viewer (только просмотр)
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def __str__(self):
        return self.name

class User(AbstractUser):
    """
    Пользователь сайта.
    Каждому пользователю назначается ОДНА роль.
    """
    role = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="users"
    )


    def has_role(self, role_name: str) -> bool:
        """Проверка роли пользователя"""
        return self.role and self.role.name == role_name

    def __str__(self):
        return self.username
