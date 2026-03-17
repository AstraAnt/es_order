import requests
from typing import Generator, List, Dict

from tsunff.utils.wb_api import (
    WB_CARDS_URL,
    WB_REQUEST_TIMEOUT,
    WB_CARDS_PAGE_LIMIT,
)


def fetch_wb_cards(api_token: str) -> Generator[List[Dict], None, None]:
    """
    Загружает карточки товаров из Wildberries по API.

    Работает через cursor-пагинацию WB.
    Возвращает генератор списков карточек.

    :param api_token: API-токен клиента WB
    :yield: список карточек товаров (cards)
    """

    # headers = {"Authorization": api_token}
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json",
    }


    body = {
        "settings": {
            "cursor": {"limit": WB_CARDS_PAGE_LIMIT},
            "filter": {"withPhoto": -1},
        }
    }

    cursor = {"total": WB_CARDS_PAGE_LIMIT}

    while cursor["total"] >= WB_CARDS_PAGE_LIMIT:
        response = requests.post(
            WB_CARDS_URL,
            headers=headers,
            json=body,
            timeout=WB_REQUEST_TIMEOUT,
        )

        # если WB вернул 4xx / 5xx — сразу ошибка
        response.raise_for_status()

        data = response.json()


        cursor = data.get("cursor", {})
        cards = data.get("cards", [])

        if not cards:
            break

        yield cards

        # обновляем курсор для следующей итерации
        body["settings"]["cursor"]["nmID"] = cursor.get("nmID")
        body["settings"]["cursor"]["updatedAt"] = cursor.get("updatedAt")