from django.db import models
from users.models import User


# class Color(models.Model):
#     name = models.CharField(max_length=100, unique=True, verbose_name='Цвет')
#
#     def __str__(self):
#         return self.name

# ---------------------------------------------------------
#  ПЛАНОВЫЙ ТОВАР (КОГДА КОД WB ЕЩЁ НЕ ИЗВЕСТЕН)
# ---------------------------------------------------------

class PlannedProduct(models.Model):
    """
    Плановый товар — используется при создании заказа,
    когда мы ещё НЕ знаем реальный Артикул ВБ и других данных.

    После появления реального товара оператор вручную связывает
    PlannedProduct <-> Product.
    """

    name = models.CharField(max_length=255, help_text="Название планового товара (придуманное нами)")
    image = models.ImageField(upload_to='planned_products/',null=True, blank=True, help_text="Фото планового товара (если есть)")
    linked_product = models.OneToOneField('orders.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name="planned_match",
        help_text="Реальный товар, с которым связали данный плановый товар")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Дата создания записи")

    def __str__(self):
        return f"Плановый товар: {self.name}"


# ---------------------------------------------------------
#  БРЕНД ТОВАРА
# ---------------------------------------------------------

class Brand(models.Model):
    """
    Бренд товара. Пример: Nike, Adidas, Xiaomi.
    """
    name = models.CharField(max_length=255, unique=True, primary_key=True,
                            help_text="Название бренда (используется как ключ)")

    def __str__(self):
        return self.name


# ---------------------------------------------------------
#  КАТЕГОРИЯ ТОВАРА
# ---------------------------------------------------------

class Category(models.Model):
    """
    Категория товаров. Пример: Shoes, Electronics, Toys.
    """
    name = models.CharField(max_length=255, unique=True, primary_key=True,
                            help_text="Название категории (используется как ключ)")

    def __str__(self):
        return self.name


# ---------------------------------------------------------
#  ОСНОВНОЙ ТОВАР (ИЗ РЕАЛЬНОГО КАТАЛОГА)
# ---------------------------------------------------------

class Product(models.Model):
    """
    Реальный товар в системе.
    wb_sku — уникальный идентификатор Wildberries (Артикул WB).
    seller_sku — внутренний код товара от поставщика. Название товара
    """
    wb_sku = models.CharField(max_length=255, unique=True, primary_key=True, help_text="Уникальный Артикул WB")
    seller_sku = models.CharField(max_length=255, help_text="Артикул продавца, Название товара")
    brand = models.ForeignKey('Brand', on_delete=models.CASCADE, related_name="products", help_text="Бренд товара")
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name="products",
                                 help_text="Категория товара")
    partner = models.ForeignKey('Partner', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="products", help_text="Владелец товара (клиент или Business Unit ИП Никита Край)")

    def __str__(self):
        return f"{self.seller_sku} {self.wb_sku}({self.category.name})"


class ProductPhoto(models.Model):
    PHOTO_TYPES = [
        ("big", "Big"),
        ("c246x328", "C246x328"),
        ("c516x688", "C516x688"),
        ("hq", "HQ"),
        ("square", "Square"),
        ("tm", "TM"),
    ]

    product = models.ForeignKey('orders.Product', on_delete=models.CASCADE, related_name="photos")
    photo_type = models.CharField(max_length=20, choices=PHOTO_TYPES)
    url = models.URLField()
    local_path = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        unique_together = ("product", "photo_type")

    def __str__(self):
        return f"{self.product.seller_sku} - {self.photo_type}"


class ProductSKU(models.Model):
    product = models.ForeignKey('orders.Product', on_delete=models.CASCADE, related_name="skus")
    barcode = models.CharField(max_length=255, unique=True, primary_key=True, db_index=True)
    tech_size = models.CharField(max_length=255)
    wb_size = models.CharField(max_length=255)
    color = models.CharField(max_length=255, default='')

    def __str__(self):
        return f"{self.product.seller_sku} - {self.barcode} "


class ProductLink(models.Model):
    """
    История сопоставлений PlannedProduct -> Product.

    Ты выбрал "вариант 2":
    - не OneToOneField в PlannedProduct
    - отдельная таблица связей

    Сейчас стоит UniqueConstraint по plan_product — это значит:
    - у одного планового товара может быть только ОДНА активная привязка.

    Если ты хочешь настоящую историю перепривязок (много записей):
    - убираем unique по plan_product
    - добавляем флаг is_active и уникальность (plan_product, is_active=True)
    """

    plan_product = models.ForeignKey("orders.PlannedProduct", on_delete=models.CASCADE, related_name="links")
    product = models.ForeignKey("orders.Product", on_delete=models.CASCADE, related_name="planned_links")

    # кто связал
    linked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # когда связал
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan_product"], name="uniq_plan_product_once"),
        ]