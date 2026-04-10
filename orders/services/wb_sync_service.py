from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from orders.models import BusinessUnit, BusinessUnitMarketplaceToken, WBSyncLog, WBSyncRun
from orders.services.wb_api import WBContentApiClient
from orders.services.wb_constants import WB_CARDS_PAGE_LIMIT
from orders.services.wb_goods_importer import import_wb_cards
from orders.services.wb_photo_downloader import download_product_photos


@dataclass
class WBSyncLogger:
    sync_run: WBSyncRun

    def info(self, stage: str, message: str, *, entity_id: str = "", entity_label: str = "") -> None:
        WBSyncLog.objects.create(
            sync_run=self.sync_run,
            level=WBSyncLog.Level.INFO,
            stage=stage,
            entity_id=entity_id,
            entity_label=entity_label,
            message=message,
        )

    def error(self, stage: str, message: str, *, entity_id: str = "", entity_label: str = "") -> None:
        WBSyncLog.objects.create(
            sync_run=self.sync_run,
            level=WBSyncLog.Level.ERROR,
            stage=stage,
            entity_id=entity_id,
            entity_label=entity_label,
            message=message,
        )


def get_wb_token(*, business_unit: BusinessUnit, token_name: str) -> BusinessUnitMarketplaceToken:
    token = (
        BusinessUnitMarketplaceToken.objects
        .filter(
            business_unit=business_unit,
            marketplace=BusinessUnitMarketplaceToken.Marketplace.WILDBERRIES,
            token_name=token_name,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )
    if not token and (not token_name or token_name == "default"):
        token = (
            BusinessUnitMarketplaceToken.objects
            .filter(
                business_unit=business_unit,
                marketplace=BusinessUnitMarketplaceToken.Marketplace.WILDBERRIES,
                is_active=True,
            )
            .order_by("-updated_at")
            .first()
        )
    if not token:
        raise ValueError(
            f"Для BU {business_unit.short_code} не найден активный WB токен с именем '{token_name}'."
        )
    if not token.token_value.strip():
        raise ValueError("Токен найден, но значение token_value пустое.")
    return token


def sync_wb_catalog(
    *,
    business_unit: BusinessUnit,
    token_name: str = "default",
    max_pages: int | None = None,
    download_photos: bool = False,
    overwrite_photos: bool = False,
    triggered_by=None,
    trigger_source: str = WBSyncRun.TriggerSource.WEB,
) -> WBSyncRun:
    sync_run = WBSyncRun.objects.create(
        business_unit=business_unit,
        triggered_by=triggered_by if getattr(triggered_by, "is_authenticated", False) else None,
        trigger_source=trigger_source,
        token_name=token_name,
        max_pages=max_pages,
        download_photos=download_photos,
        overwrite_photos=overwrite_photos,
        status=WBSyncRun.Status.RUNNING,
    )
    logger = WBSyncLogger(sync_run=sync_run)
    logger.info(
        WBSyncLog.Stage.SYSTEM,
        f"Запуск синка для {business_unit.short_code}. token_name={token_name}, download_photos={download_photos}.",
    )

    try:
        token = get_wb_token(business_unit=business_unit, token_name=token_name)
        sync_run.token_name = token.token_name
        sync_run.save(update_fields=["token_name"])
        client = WBContentApiClient(token.token_value)

        cards: list[dict] = []
        cursor = None
        page = 0
        page_fetch_error = None

        while True:
            next_page = page + 1
            try:
                page_cards, next_cursor = client.fetch_cards_page(cursor=cursor, limit=WB_CARDS_PAGE_LIMIT)
            except Exception as exc:
                page_fetch_error = str(exc)
                logger.error(
                    WBSyncLog.Stage.PAGE,
                    f"Ошибка загрузки страницы {next_page}: {exc}",
                    entity_id=str(next_page),
                )
                break

            page = next_page
            if not page_cards:
                logger.info(WBSyncLog.Stage.PAGE, f"Страница {page}: карточек не найдено, завершение.")
                page -= 1
                break

            cards.extend(page_cards)
            logger.info(WBSyncLog.Stage.PAGE, f"Страница {page}: получено карточек {len(page_cards)}.")

            if len(page_cards) < WB_CARDS_PAGE_LIMIT:
                break
            if max_pages is not None and page >= max_pages:
                logger.info(WBSyncLog.Stage.PAGE, f"Остановлено по лимиту max_pages={max_pages}.")
                break
            if cursor and cursor.updated_at == next_cursor.updated_at and cursor.nm_id == next_cursor.nm_id:
                logger.info(WBSyncLog.Stage.PAGE, "Курсор WB не изменился, дальнейшая пагинация остановлена.")
                break

            cursor = next_cursor

        import_stats = import_wb_cards(cards, business_unit, logger=logger)
        for field in (
            "cards_total",
            "failed_cards",
            "new_products",
            "updated_products",
            "new_skus",
            "updated_skus",
            "new_photos",
            "updated_photos",
        ):
            setattr(sync_run, field, import_stats[field])
        sync_run.pages_total = page

        if download_photos:
            photo_stats = download_product_photos(
                business_unit=business_unit,
                overwrite=overwrite_photos,
                logger=logger,
            )
            sync_run.photos_total = photo_stats["total"]
            sync_run.photos_downloaded = photo_stats["downloaded"]
            sync_run.photos_skipped = photo_stats["skipped"]
            sync_run.photos_failed = photo_stats["failed"]

        if page_fetch_error:
            sync_run.error_message = page_fetch_error
        sync_run.status = (
            WBSyncRun.Status.PARTIAL
            if page_fetch_error or sync_run.failed_cards or sync_run.photos_failed
            else WBSyncRun.Status.SUCCESS
        )
        sync_run.completed_at = timezone.now()
        sync_run.save()
        logger.info(
            WBSyncLog.Stage.SYSTEM,
            "Синк завершён."
            f" cards={sync_run.cards_total}, failed_cards={sync_run.failed_cards},"
            f" photos_failed={sync_run.photos_failed}, page_error={'yes' if page_fetch_error else 'no'}.",
        )
        return sync_run
    except Exception as exc:
        sync_run.status = WBSyncRun.Status.FAILED
        sync_run.error_message = str(exc)
        sync_run.completed_at = timezone.now()
        sync_run.save(update_fields=["status", "error_message", "completed_at"])
        logger.error(WBSyncLog.Stage.SYSTEM, f"Синк завершился ошибкой: {exc}")
        raise
