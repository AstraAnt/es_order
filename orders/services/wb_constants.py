"""
Константы и базовые настройки Wildberries Content API.
"""

WB_API_BASE = "https://content-api.wildberries.ru"

WB_CARDS_URL = f"{WB_API_BASE}/content/v2/get/cards/list"

WB_REQUEST_TIMEOUT = 30
WB_CARDS_PAGE_LIMIT = 100
WB_REQUEST_RETRIES = 3
