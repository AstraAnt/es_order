from django.db import models



class PartnerMarketplaceToken(models.Model):
    class Marketplace(models.TextChoices):
        WILDBERRIES = "wb", "Wildberries"
        OZON = "ozon", "Ozon"
        YANDEX_MARKET = "ym", "Yandex Market"

    partner = models.ForeignKey(
        "Partner",
        on_delete=models.CASCADE,
        related_name="marketplace_tokens",
    )

    marketplace = models.CharField(
        max_length=16,
        choices=Marketplace.choices,
        help_text="Маркетплейс"
    )

    token_name = models.CharField(
        max_length=64,
        help_text="Название токена (например statistics, analytics, orders_api)"
    )

    token_value = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Значение токена"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Активен ли токен"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["partner"]),
            models.Index(fields=["partner", "marketplace"]),
            models.Index(fields=["partner", "marketplace", "token_name"]),
        ]

    def __str__(self):
        return f"{self.partner} / {self.marketplace}:{self.token_name}"