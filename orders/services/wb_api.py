from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Iterable
from urllib import error, request

from .wb_constants import WB_CARDS_PAGE_LIMIT, WB_CARDS_URL, WB_REQUEST_RETRIES, WB_REQUEST_TIMEOUT


class WildberriesApiError(Exception):
    pass


def build_wb_auth_header(token: str) -> str:
    token = (token or "").strip()
    if not token:
        raise WildberriesApiError("Пустой API-токен Wildberries.")
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


@dataclass
class WBCardsCursor:
    updated_at: str | None = None
    nm_id: int | None = None


class WBContentApiClient:
    def __init__(self, token: str, timeout: int = WB_REQUEST_TIMEOUT, retries: int = WB_REQUEST_RETRIES):
        self.timeout = timeout
        self.retries = max(1, retries)
        self.headers = {
            "Authorization": build_wb_auth_header(token),
            "Content-Type": "application/json",
        }

    def fetch_cards_page(self, cursor: WBCardsCursor | None = None, limit: int = WB_CARDS_PAGE_LIMIT):
        payload = {
            "settings": {
                "cursor": {
                    "limit": limit,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        }

        if cursor and cursor.updated_at:
            payload["settings"]["cursor"]["updatedAt"] = cursor.updated_at
        if cursor and cursor.nm_id:
            payload["settings"]["cursor"]["nmID"] = cursor.nm_id

        body = json.dumps(payload).encode("utf-8")
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                req = request.Request(WB_CARDS_URL, data=body, headers=self.headers, method="POST")
                with request.urlopen(req, timeout=self.timeout) as response:
                    raw_data = response.read().decode("utf-8")
                break
            except error.HTTPError as exc:
                raise WildberriesApiError(
                    f"Ошибка запроса к Wildberries: {exc.code} {exc.read().decode('utf-8', errors='ignore')[:300]}"
                ) from exc
            except (error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    reason = getattr(exc, "reason", exc)
                    raise WildberriesApiError(
                        f"Ошибка соединения с Wildberries после {self.retries} попыток: {reason}"
                    ) from exc
                time.sleep(min(attempt, 3))

        data = json.loads(raw_data)
        cards = data.get("cards") or []
        raw_cursor = data.get("cursor") or {}
        next_cursor = WBCardsCursor(
            updated_at=raw_cursor.get("updatedAt"),
            nm_id=raw_cursor.get("nmID"),
        )
        return cards, next_cursor

    def iter_cards(self, limit: int = WB_CARDS_PAGE_LIMIT, max_pages: int | None = None) -> Iterable[dict]:
        cursor = None
        page = 0

        while True:
            page += 1
            cards, next_cursor = self.fetch_cards_page(cursor=cursor, limit=limit)
            if not cards:
                break

            for card in cards:
                yield card

            if len(cards) < limit:
                break
            if max_pages is not None and page >= max_pages:
                break
            if cursor and cursor.updated_at == next_cursor.updated_at and cursor.nm_id == next_cursor.nm_id:
                break

            cursor = next_cursor
