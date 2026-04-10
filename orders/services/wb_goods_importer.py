from __future__ import annotations

from django.db import transaction

from orders.models import Brand, BusinessUnit, Category, Product, ProductPhoto, ProductSKU
from orders.models import WBSyncLog


def _extract_color(card: dict) -> str:
    for item in card.get("characteristics", []):
        if item.get("name") == "Цвет" and item.get("value"):
            value = item["value"]
            if isinstance(value, list):
                return str(value[0])
            return str(value)
    return ""


def import_wb_cards(cards: list[dict], business_unit: BusinessUnit, logger=None) -> dict:
    changes: list[str] = []

    brands = Brand.objects.in_bulk(field_name="name")
    categories = Category.objects.in_bulk(field_name="name")
    products = Product.objects.in_bulk(field_name="wb_sku")
    skus = ProductSKU.objects.select_related("product").in_bulk(field_name="barcode")
    photos = {
        (photo.product_id, photo.photo_type): photo
        for photo in ProductPhoto.objects.select_related("product").all()
    }

    new_brands = []
    new_categories = []
    new_products = []
    new_skus = []
    new_photos = []

    updated_products = []
    updated_skus = []
    updated_photos = []
    failed_cards = 0

    for card in cards:
        try:
            brand_name = str(card.get("brand") or "Без бренда")
            category_name = str(card.get("subjectName") or "Без категории")
            wb_sku = str(card.get("nmID"))
            seller_sku = str(card.get("vendorCode") or wb_sku)

            if not wb_sku or wb_sku == "None":
                raise ValueError("У карточки отсутствует nmID.")

            brand = brands.get(brand_name)
            if not brand:
                brand = Brand(name=brand_name)
                brands[brand_name] = brand
                new_brands.append(brand)

            category = categories.get(category_name)
            if not category:
                category = Category(name=category_name)
                categories[category_name] = category
                new_categories.append(category)

            product = products.get(wb_sku)
            card_action = "updated"
            if not product:
                product = Product(
                    wb_sku=wb_sku,
                    seller_sku=seller_sku,
                    brand=brand,
                    category=category,
                    business_unit=business_unit,
                )
                products[wb_sku] = product
                new_products.append(product)
                card_action = "created"
                changes.append(f"Новый товар: {seller_sku} ({wb_sku})")
            else:
                changed = False
                if product.seller_sku != seller_sku:
                    product.seller_sku = seller_sku
                    changed = True
                if product.brand_id != brand.name:
                    product.brand = brand
                    changed = True
                if product.category_id != category.name:
                    product.category = category
                    changed = True
                if product.business_unit_id != business_unit.id:
                    product.business_unit = business_unit
                    changed = True
                if changed:
                    updated_products.append(product)
                else:
                    card_action = "unchanged"

            color = _extract_color(card)
            for size in card.get("sizes", []):
                tech_size = str(size.get("techSize") or "")
                wb_size = str(size.get("wbSize") or "")
                for barcode in size.get("skus", []):
                    barcode = str(barcode)
                    sku = skus.get(barcode)
                    if sku:
                        changed = False
                        if sku.product_id != product.wb_sku:
                            sku.product = product
                            changed = True
                        if sku.tech_size != tech_size:
                            sku.tech_size = tech_size
                            changed = True
                        if sku.wb_size != wb_size:
                            sku.wb_size = wb_size
                            changed = True
                        if sku.color != color:
                            sku.color = color
                            changed = True
                        if changed:
                            updated_skus.append(sku)
                    else:
                        sku = ProductSKU(
                            product=product,
                            barcode=barcode,
                            tech_size=tech_size,
                            wb_size=wb_size,
                            color=color,
                        )
                        skus[barcode] = sku
                        new_skus.append(sku)

            for photo in card.get("photos", []):
                for photo_type in ("big", "c246x328"):
                    url = photo.get(photo_type)
                    if not url:
                        continue
                    key = (product.wb_sku, photo_type)
                    existing = photos.get(key)
                    if existing:
                        if existing.url != url:
                            existing.url = url
                            if existing.pk:
                                updated_photos.append(existing)
                    else:
                        existing = ProductPhoto(
                            product=product,
                            photo_type=photo_type,
                            url=url,
                        )
                        photos[key] = existing
                        new_photos.append(existing)

            if logger:
                logger.info(
                    WBSyncLog.Stage.CARD,
                    f"Карточка {card_action}: SKU {seller_sku}, бренд {brand_name}, категория {category_name}.",
                    entity_id=wb_sku,
                    entity_label=seller_sku,
                )
        except Exception as exc:
            failed_cards += 1
            if logger:
                logger.error(
                    WBSyncLog.Stage.CARD,
                    f"Ошибка обработки карточки: {exc}",
                    entity_id=str(card.get('nmID') or ""),
                    entity_label=str(card.get('vendorCode') or ""),
                )

    with transaction.atomic():
        Brand.objects.bulk_create(new_brands, ignore_conflicts=True)
        Category.objects.bulk_create(new_categories, ignore_conflicts=True)
        Product.objects.bulk_create(new_products, ignore_conflicts=True)

        if updated_products:
            Product.objects.bulk_update(updated_products, ["seller_sku", "brand", "category", "business_unit"])

        ProductSKU.objects.bulk_create(new_skus, ignore_conflicts=True)
        if updated_skus:
            ProductSKU.objects.bulk_update(updated_skus, ["product", "tech_size", "wb_size", "color"])

        ProductPhoto.objects.bulk_create(new_photos, ignore_conflicts=True)
        if updated_photos:
            ProductPhoto.objects.bulk_update(updated_photos, ["url"])

    return {
        "cards_total": len(cards),
        "failed_cards": failed_cards,
        "new_products": len(new_products),
        "updated_products": len(updated_products),
        "new_skus": len(new_skus),
        "updated_skus": len(updated_skus),
        "new_photos": len(new_photos),
        "updated_photos": len(updated_photos),
        "changes": changes,
    }
