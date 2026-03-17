
MENU_BY_ROLE = {
    "admin": [
        {"title": "Панель администратора",  "url": "tsunff:admin_dashboard"},
        # {"title": "Менеджер",               "url": "tsunff:manager_dashboard"},
        {"title": "плановый товар",         "url": "tsunff:planned_product_create"},
        {"title": "Товары",                 "url": "tsunff:products_list_GPT"},
        {"title": "Загрузить товары",       "url": "tsunff:goodskt"},
        {"title": "Загрузить фото",         "url": "tsunff:download_photos"},
        {"title": "связь товаров",          "url": "tsunff:product_linking"},
        {"title": "Админка Django",         "url": "admin:index"},

    ],
    "owner": [
        {"title": "Панель администратора", "url": "tsunff:admin_dashboard"},
        {"title": "Менеджер", "url": "tsunff:manager_dashboard"},
        {"title": "Склад", "url": "tsunff:warehouse_dashboard"},
    ],

    "manager": [
        {"title": "Менеджер", "url": "tsunff:manager_dashboard"},
    ],

    "warehouse": [
        {"title": "Склад", "url": "tsunff:warehouse_dashboard"},
    ],
}
