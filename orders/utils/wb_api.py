"""
Все константы и базовые настройки Wildberries API
"""

# ---------- BASE URL ----------
WB_API_BASE = "https://content-api.wildberries.ru"

# ---------- ENDPOINTS ----------
WB_CARDS_URL = f"{WB_API_BASE}/content/v2/get/cards/list"
WB_PHOTOS_URL = "https://basket-01.wb.ru/vol0/part0/{}"

# ---------- TIMEOUTS ----------
WB_REQUEST_TIMEOUT = 15

# ---------- LIMITS ----------
WB_CARDS_PAGE_LIMIT = 100
