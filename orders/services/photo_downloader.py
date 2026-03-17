import os
import requests
from django.conf import settings
from tsunff.models.product import ProductPhoto


def build_photo_path(photo: ProductPhoto) -> tuple[str, str]:
    """
    Формирует путь для сохранения фото.

    Возвращает:
        absolute_path — полный путь на диске
        relative_path — путь для сохранения в БД
    """
    client_name = photo.product.client.name if photo.product.client else "Без_клиента"
    seller_sku = photo.product.seller_sku.replace("/", "_")
    photo_type = photo.photo_type

    # MEDIA_ROOT/photos/Клиент/Артикул/
    base_dir = os.path.join(
        settings.MEDIA_ROOT,
        "photos",
        client_name,
        seller_sku,
    )

    os.makedirs(base_dir, exist_ok=True)


    absolute_path = os.path.join(base_dir, f"{photo_type}.jpg")
    relative_path = os.path.relpath(absolute_path, settings.MEDIA_ROOT).replace("\\", "/")

    # 🔹 ВАЖНО: без "media/"
    return absolute_path, relative_path

def download_photo(photo: ProductPhoto) -> bool:
    """
    Скачивает одно фото и сохраняет путь в БД.
    """
    try:
        response = requests.get(photo.url, timeout=10)

        if response.status_code != 200:
            return False

        abs_path, db_path = build_photo_path(photo)

        with open(abs_path, "wb") as file:
            file.write(response.content)

        photo.local_path = db_path
        photo.save(update_fields=["local_path"])

        return True

    except requests.RequestException:
        return False


def download_all_photos() -> dict:
    """
    Загружает ВСЕ фото из БД.

    Возвращает статистику.
    """
    photos = ProductPhoto.objects.select_related("product__client")

    stats = {
        "total": photos.count(),
        "success": 0,
        "failed": 0,
    }

    for photo in photos:
        if download_photo(photo):
            stats["success"] += 1
        else:
            stats["failed"] += 1

    return stats
