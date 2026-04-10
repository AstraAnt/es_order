import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_product_business_unit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WBSyncRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("trigger_source", models.CharField(choices=[("web", "Web"), ("admin", "Admin"), ("command", "Command")], default="web", max_length=20)),
                ("token_name", models.CharField(default="default", max_length=100)),
                ("max_pages", models.PositiveIntegerField(blank=True, null=True)),
                ("download_photos", models.BooleanField(default=False)),
                ("overwrite_photos", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("running", "Running"), ("success", "Success"), ("partial", "Partial"), ("failed", "Failed")], default="running", max_length=20)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("pages_total", models.PositiveIntegerField(default=0)),
                ("cards_total", models.PositiveIntegerField(default=0)),
                ("failed_cards", models.PositiveIntegerField(default=0)),
                ("new_products", models.PositiveIntegerField(default=0)),
                ("updated_products", models.PositiveIntegerField(default=0)),
                ("new_skus", models.PositiveIntegerField(default=0)),
                ("updated_skus", models.PositiveIntegerField(default=0)),
                ("new_photos", models.PositiveIntegerField(default=0)),
                ("updated_photos", models.PositiveIntegerField(default=0)),
                ("photos_total", models.PositiveIntegerField(default=0)),
                ("photos_downloaded", models.PositiveIntegerField(default=0)),
                ("photos_skipped", models.PositiveIntegerField(default=0)),
                ("photos_failed", models.PositiveIntegerField(default=0)),
                ("business_unit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wb_sync_runs", to="orders.businessunit")),
                ("triggered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wb_sync_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "WB Sync Run",
                "verbose_name_plural": "WB Sync Runs",
                "ordering": ("-started_at",),
            },
        ),
        migrations.CreateModel(
            name="WBSyncLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("level", models.CharField(choices=[("info", "Info"), ("error", "Error")], default="info", max_length=10)),
                ("stage", models.CharField(choices=[("system", "System"), ("page", "Page"), ("card", "Card"), ("photo", "Photo")], default="system", max_length=20)),
                ("entity_id", models.CharField(blank=True, default="", max_length=255)),
                ("entity_label", models.CharField(blank=True, default="", max_length=255)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sync_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="logs", to="orders.wbsyncrun")),
            ],
            options={
                "verbose_name": "WB Sync Log",
                "verbose_name_plural": "WB Sync Logs",
                "ordering": ("created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="wbsyncrun",
            index=models.Index(fields=["business_unit", "started_at"], name="orders_wbsy_busines_8e2240_idx"),
        ),
        migrations.AddIndex(
            model_name="wbsyncrun",
            index=models.Index(fields=["status", "started_at"], name="orders_wbsy_status_84f3db_idx"),
        ),
        migrations.AddIndex(
            model_name="wbsynclog",
            index=models.Index(fields=["sync_run", "created_at"], name="orders_wbsy_sync_ru_74ebea_idx"),
        ),
        migrations.AddIndex(
            model_name="wbsynclog",
            index=models.Index(fields=["stage", "level"], name="orders_wbsy_stage_0a03f3_idx"),
        ),
    ]
