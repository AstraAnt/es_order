from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from orders.models import BusinessUnit, WBSyncRun
from orders.services.wb_sync_service import get_wb_token, sync_wb_catalog


class Command(BaseCommand):
    help = "Загружает карточки товаров и фото из Wildberries по токену Business Unit."

    def add_arguments(self, parser):
        parser.add_argument("--business-unit-id", help="UUID Business Unit")
        parser.add_argument("--business-unit-code", help="short_code Business Unit")
        parser.add_argument("--token-name", default="default", help="Имя токена WB внутри Business Unit")
        parser.add_argument("--max-pages", type=int, default=None, help="Ограничить число страниц API")
        parser.add_argument("--download-photos", action="store_true", help="Сразу скачать фото после импорта")
        parser.add_argument("--overwrite-photos", action="store_true", help="Перезаписать уже скачанные фото")

    def handle(self, *args, **options):
        business_unit = self._resolve_business_unit(
            options.get("business_unit_id"),
            options.get("business_unit_code"),
        )
        try:
            get_wb_token(business_unit=business_unit, token_name=options["token_name"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        try:
            sync_run = sync_wb_catalog(
                business_unit=business_unit,
                token_name=options["token_name"],
                max_pages=options["max_pages"],
                download_photos=options["download_photos"],
                overwrite_photos=options["overwrite_photos"],
                trigger_source=WBSyncRun.TriggerSource.COMMAND,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"WB import complete for {business_unit.short_code}: "
            f"pages={sync_run.pages_total}, cards={sync_run.cards_total}, failed_cards={sync_run.failed_cards}, "
            f"new_products={sync_run.new_products}, updated_products={sync_run.updated_products}, "
            f"new_skus={sync_run.new_skus}, updated_skus={sync_run.updated_skus}, "
            f"new_photos={sync_run.new_photos}, updated_photos={sync_run.updated_photos}"
        ))

        if options["download_photos"]:
            self.stdout.write(self.style.SUCCESS(
                f"Photo sync complete: total={sync_run.photos_total}, "
                f"downloaded={sync_run.photos_downloaded}, skipped={sync_run.photos_skipped}, "
                f"failed={sync_run.photos_failed}"
            ))

    def _resolve_business_unit(self, business_unit_id, business_unit_code):
        if not business_unit_id and not business_unit_code:
            raise CommandError("Укажите --business-unit-id или --business-unit-code")

        queryset = BusinessUnit.objects.filter(is_active=True)
        if business_unit_id:
            business_unit = queryset.filter(id=business_unit_id).first()
        else:
            business_unit = queryset.filter(short_code=business_unit_code.upper()).first()

        if not business_unit:
            raise CommandError("Business Unit не найден или не активен.")
        return business_unit
