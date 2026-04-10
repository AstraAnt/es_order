import uuid

from django.conf import settings
from django.db import models


class WBSyncRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    class TriggerSource(models.TextChoices):
        WEB = "web", "Web"
        ADMIN = "admin", "Admin"
        COMMAND = "command", "Command"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_unit = models.ForeignKey(
        "orders.BusinessUnit",
        on_delete=models.CASCADE,
        related_name="wb_sync_runs",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wb_sync_runs",
    )
    trigger_source = models.CharField(max_length=20, choices=TriggerSource.choices, default=TriggerSource.WEB)
    token_name = models.CharField(max_length=100, default="default")
    max_pages = models.PositiveIntegerField(null=True, blank=True)
    download_photos = models.BooleanField(default=False)
    overwrite_photos = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    pages_total = models.PositiveIntegerField(default=0)
    cards_total = models.PositiveIntegerField(default=0)
    failed_cards = models.PositiveIntegerField(default=0)
    new_products = models.PositiveIntegerField(default=0)
    updated_products = models.PositiveIntegerField(default=0)
    new_skus = models.PositiveIntegerField(default=0)
    updated_skus = models.PositiveIntegerField(default=0)
    new_photos = models.PositiveIntegerField(default=0)
    updated_photos = models.PositiveIntegerField(default=0)
    photos_total = models.PositiveIntegerField(default=0)
    photos_downloaded = models.PositiveIntegerField(default=0)
    photos_skipped = models.PositiveIntegerField(default=0)
    photos_failed = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "WB Sync Run"
        verbose_name_plural = "WB Sync Runs"
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=["business_unit", "started_at"]),
            models.Index(fields=["status", "started_at"]),
        ]

    def __str__(self):
        return f"WB sync {self.business_unit.short_code} {self.started_at:%Y-%m-%d %H:%M}"


class WBSyncLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        ERROR = "error", "Error"

    class Stage(models.TextChoices):
        SYSTEM = "system", "System"
        PAGE = "page", "Page"
        CARD = "card", "Card"
        PHOTO = "photo", "Photo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_run = models.ForeignKey(
        "orders.WBSyncRun",
        on_delete=models.CASCADE,
        related_name="logs",
    )
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.SYSTEM)
    entity_id = models.CharField(max_length=255, blank=True, default="")
    entity_label = models.CharField(max_length=255, blank=True, default="")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "WB Sync Log"
        verbose_name_plural = "WB Sync Logs"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["sync_run", "created_at"]),
            models.Index(fields=["stage", "level"]),
        ]

    def __str__(self):
        return f"{self.sync_run_id} {self.stage} {self.level}"
