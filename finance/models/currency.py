from django.core.exceptions import ValidationError
from django.db import models


class Currency(models.Model):
    """
    Валюта.

    Зачем вообще отдельная таблица, а не просто CharField("USD"):
    - чтобы иметь единый справочник (код, название, символ)
    - чтобы можно было выключать валюты (is_active)
    - чтобы не плодить “кривые” коды (usd / Usd / U$ / и т.д.)
    - чтобы делать FK из заказов и проекций

    В ES (Event Sourcing):
    - В событиях мы храним currency_id (UUID/PK), чтобы состояние было воспроизводимым.
    - В read-model (OrderView) можно хранить FK на Currency (как мы сделали).
    """

    # Обычно удобно использовать ISO 4217 код как первичный ключ: "RUB", "USD", "CNY"
    code = models.CharField(
        max_length=3,
        primary_key=True,
        help_text="Код валюты ISO 4217 (например: RUB, USD, CNY)",
    )

    name = models.CharField(
        max_length=64,
        help_text="Название валюты (например: Российский рубль)",
    )

    symbol = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Символ валюты (₽, $, ¥). Не обязателен.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Можно ли выбирать эту валюту в новых документах",
    )

    class Meta:
        verbose_name = "Валюта"
        verbose_name_plural = "Валюты"
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def clean(self):
        """
        Приводим код к верхнему регистру и проверяем формат.
        """
        self.code = (self.code or "").upper().strip()

        if len(self.code) != 3:
            raise ValidationError({"code": "Код валюты должен быть длиной ровно 3 символа (ISO 4217)."})
        if not self.code.isalpha():
            raise ValidationError({"code": "Код валюты должен содержать только буквы (например: RUB, USD)."})

    def save(self, *args, **kwargs):
        # Гарантируем, что clean() всегда отработает и данные будут нормальными
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"