from django.db import transaction

from tsunff.models.product import  (
    Brand, Category, Product, ProductSKU, ProductPhoto
)


def import_cards(cards, client):
    """
    Импортирует карточки WB в базу данных.

    :param cards: список карточек WB
    :param client: Client объект
    :return: список изменений (str)
    """

    changes = []

    # Кэш существующих данных
    brands = Brand.objects.in_bulk(field_name="name")
    categories = Category.objects.in_bulk(field_name="name")
    products = Product.objects.in_bulk(field_name="wb_sku")

    skus = ProductSKU.objects.in_bulk(field_name="barcode")

    new_brands = []
    new_categories = []
    new_products = []
    new_skus = []
    new_photos = []
    updated_skus = []

    for card in cards:

        # ---------- БРЕНД ----------
        brand = brands.get(card["brand"])
        if not brand:
            brand = Brand(name=card["brand"])
            new_brands.append(brand)
            brands[card["brand"]] = brand
            changes.append(f"Новый бренд: {card['brand']}")

        # ---------- КАТЕГОРИЯ ----------
        category = categories.get(card["subjectName"])
        if not category:
            category = Category(name=card["subjectName"])
            new_categories.append(category)
            categories[card["subjectName"]] = category
            changes.append(f"Новая категория: {card['subjectName']}")

        # ---------- ТОВАР ----------
        product = products.get(card["nmID"])
        if not product:
            product = Product(
                wb_sku=card["nmID"],
                seller_sku=card["vendorCode"],
                brand=brand,
                category=category,
                client=client
            )
            new_products.append(product)
            products[card["nmID"]] = product

        # ---------- SKU ----------
        for size in card["sizes"]:
            barcode = size["skus"][0]

            color = ""
            for char in card.get("characteristics", []):
                if char["name"] == "Цвет" and char["value"]:
                    color = char["value"][0]

            sku = skus.get(barcode)

            if sku:
                if (
                    sku.tech_size != size["techSize"] or
                    sku.wb_size != size["wbSize"] or
                    sku.color != color
                ):
                    sku.tech_size = size["techSize"]
                    sku.wb_size = size["wbSize"]
                    sku.color = color
                    updated_skus.append(sku)
                    changes.append(f"Обновлён баркод {barcode}")
            else:
                new_skus.append(ProductSKU(
                    product=product,
                    barcode=barcode,
                    tech_size=size["techSize"],
                    wb_size=size["wbSize"],
                    color=color
                ))
                changes.append(f"Добавлен баркод {barcode}")

        # ---------- ФОТО ----------

        for photo in card.get("photos", []):
            for photo_type in ["big", "c246x328"]:
                if photo_type in photo:
                    new_photos.append(ProductPhoto(
                        product=product,
                        photo_type=photo_type,
                        url=photo[photo_type]
                    ))

    with transaction.atomic():
        Brand.objects.bulk_create(new_brands, ignore_conflicts=True)
        Category.objects.bulk_create(new_categories, ignore_conflicts=True)
        Product.objects.bulk_create(new_products, ignore_conflicts=True)
        ProductSKU.objects.bulk_create(new_skus, ignore_conflicts=True)
        ProductPhoto.objects.bulk_create(new_photos, ignore_conflicts=True)

        if updated_skus:
            ProductSKU.objects.bulk_update(
                updated_skus, ["tech_size", "wb_size", "color"]
            )

    return changes or ["Изменений нет"]
