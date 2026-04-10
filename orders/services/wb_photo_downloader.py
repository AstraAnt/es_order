from __future__ import annotations

from pathlib import Path
from urllib import error, request
from django.conf import settings

from orders.models import ProductPhoto
from orders.models import WBSyncLog


def build_photo_path(photo: ProductPhoto) -> tuple[Path, str]:
    business_unit_name = photo.product.business_unit.name if photo.product.business_unit else "Без_BU"
    safe_bu = business_unit_name.replace("/", "_").replace("\\", "_")
    safe_sku = photo.product.seller_sku.replace("/", "_").replace("\\", "_")

    base_dir = Path(settings.MEDIA_ROOT) / "photos" / safe_bu / safe_sku
    base_dir.mkdir(parents=True, exist_ok=True)

    absolute_path = base_dir / f"{photo.photo_type}.jpg"
    relative_path = absolute_path.relative_to(settings.MEDIA_ROOT).as_posix()
    return absolute_path, relative_path


def download_photo(photo: ProductPhoto, overwrite: bool = False, timeout: int = 10) -> str:
    absolute_path, relative_path = build_photo_path(photo)
    if absolute_path.exists() and photo.local_path and not overwrite:
        return "skipped"

    with request.urlopen(photo.url, timeout=timeout) as response:
        absolute_path.write_bytes(response.read())
    photo.local_path = relative_path
    photo.save(update_fields=["local_path"])
    return "downloaded"


def download_product_photos(*, business_unit=None, overwrite: bool = False, logger=None) -> dict:
    photos = ProductPhoto.objects.select_related("product__business_unit")
    if business_unit is not None:
        photos = photos.filter(product__business_unit=business_unit)

    stats = {
        "total": photos.count(),
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
    }

    for photo in photos:
        try:
            result = download_photo(photo, overwrite=overwrite)
            stats[result] += 1
            if logger:
                logger.info(
                    WBSyncLog.Stage.PHOTO,
                    f"Фото {result}: {photo.photo_type}.",
                    entity_id=photo.product_id,
                    entity_label=photo.product.seller_sku,
                )
        except Exception as exc:
            stats["failed"] += 1
            if logger:
                logger.error(
                    WBSyncLog.Stage.PHOTO,
                    f"Ошибка загрузки фото {photo.photo_type}: {exc}",
                    entity_id=photo.product_id,
                    entity_label=photo.product.seller_sku,
                )

    return stats
