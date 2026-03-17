from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    """
    Доменное событие (в памяти).
    Потом мы сериализуем его в таблицу Event.
    """
    event_type: str
    aggregate_id: UUID
    occurred_at: datetime
    payload: Dict[str, Any]
    metadata: Dict[str, Any]


# --- События уровня заказа ---
ORDER_CREATED = "OrderCreated"
ORDER_UPDATED = "OrderUpdated"
ORDER_CANCELLED = "OrderCancelled"

# --- События уровня позиций ---
ORDER_ITEM_ADDED = "OrderItemAdded"
ORDER_ITEM_REMOVED = "OrderItemRemoved"
ORDER_ITEM_QTY_SET = "OrderItemQuantitySet"
ORDER_ITEM_PRICE_SET = "OrderItemPriceSet"

# --- Поля планирования/сопоставления ---
ORDER_ITEM_FX_PLANNED_SET = "OrderItemFxPlannedSet"
ORDER_ITEM_RESOLVED_TO_BARCODE = "OrderItemResolvedToBarcode"
