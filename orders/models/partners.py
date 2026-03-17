import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models


def normalize_code(raw: str) -> str:
    s = (raw or "").upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


class Partner(models.Model):
    """
    Внешний / операционный контрагент.

    ВАЖНО:
    - Business Unit больше НЕ лежит здесь
    - здесь только реальные контрагенты:
      supplier / buyer / manufacturer
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Role(models.TextChoices):
        SUPPLIER = "supplier", "Supplier"
        BUYER = "buyer", "Buyer"
        MANUFACTURER = "manufacturer", "Manufacturer"

    name = models.CharField(max_length=255, unique=True)
    short_code = models.CharField(max_length=3, unique=True)
    roles = models.ManyToManyField("PartnerRole", blank=True, related_name="partners")

    inn = models.CharField(max_length=12, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.CharField(max_length=300, blank=True, default="")
    note = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Partner"
        verbose_name_plural = "Partners"
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

    def has_role(self, role_code: str) -> bool:
        return self.roles.filter(code=role_code).exists()

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class PartnerRole(models.Model):
    """
    Справочник ролей партнёров.
    """
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=64)

    class Meta:
        verbose_name = "Partner Role"
        verbose_name_plural = "Partner Roles"

    def __str__(self):
        return self.title