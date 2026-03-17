import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models


def normalize_code(raw: str) -> str:
    """
    Нормализация короткого кода:
    - верхний регистр
    - только A-Z / 0-9
    """
    s = (raw or "").upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


class BusinessUnit(models.Model):
    """
    Внутренний бизнес-юнит холдинга.

    Это НЕ Partner.
    Это отдельная внутренняя сущность, с которой:
    - связываются заказы
    - связываются токены маркетплейсов
    - работают пользователи через выбор активного BU в сессии
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255, unique=True)
    short_code = models.CharField(max_length=3, unique=True)

    # Общие реквизиты / контакты
    inn = models.CharField(max_length=12, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.CharField(max_length=300, blank=True, default="")
    note = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Business Unit"
        verbose_name_plural = "Business Units"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["short_code"]),
        ]

    def clean(self):
        self.short_code = normalize_code(self.short_code)

        if not self.short_code:
            raise ValidationError({"short_code": "Код обязателен (1–3 символа A-Z/0-9)."})

        if len(self.short_code) > 3:
            raise ValidationError({"short_code": "Код должен быть не длиннее 3 символов."})

        if not re.fullmatch(r"[A-Z0-9]{1,3}", self.short_code):
            raise ValidationError({"short_code": "Только A-Z и 0-9."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class BusinessUnitMarketplaceToken(models.Model):
    """
    Токены маркетплейсов принадлежат именно Business Unit.

    Это логично, потому что:
    - токены — внутренний доступ холдинга
    - они не относятся к внешним контрагентам (Partner)
    """

    class Marketplace(models.TextChoices):
        WILDBERRIES = "wb", "Wildberries"
        OZON = "ozon", "Ozon"
        YANDEX_MARKET = "ym", "Yandex Market"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    business_unit = models.ForeignKey(
        "BusinessUnit",
        on_delete=models.CASCADE,
        related_name="marketplace_tokens",
    )

    marketplace = models.CharField(max_length=20, choices=Marketplace.choices)
    token_name = models.CharField(
        max_length=100,
        default="default",
        help_text="Имя токена внутри маркетплейса, если у одного BU может быть несколько токенов",
    )
    token_value = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Business Unit Marketplace Token"
        verbose_name_plural = "Business Unit Marketplace Tokens"
        constraints = [
            models.UniqueConstraint(
                fields=["business_unit", "marketplace", "token_name"],
                name="uniq_bu_marketplace_token_name",
            )
        ]
        indexes = [
            models.Index(fields=["marketplace", "is_active"]),
        ]

    def __str__(self):
        return f"{self.business_unit.short_code} / {self.marketplace} / {self.token_name}"

    def masked_value(self) -> str:
        """
        Удобно для админки/логов, чтобы не светить токен целиком.
        """
        if not self.token_value:
            return ""
        if len(self.token_value) <= 8:
            return "*" * len(self.token_value)
        return f"{self.token_value[:4]}***{self.token_value[-4:]}"