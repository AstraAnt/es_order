from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import date


@dataclass(frozen=True)
class CreateOrder:
    order_id: UUID

    human_code: str  # можно передать вручную или "" для автогенерации
    date: date

    business_unit_id: UUID
    buyer_id: UUID

    currency_id: str  # "RUB" / "USD" / "CNY"

    notes: Optional[str] = None

    buyer_commission_percent: Optional[Decimal] = None
    buyer_commission_amount: Optional[Decimal] = None
    buyer_delivery_cost: Decimal = Decimal("0")


@dataclass(frozen=True)
class UpdateOrder:
    order_id: UUID

    buyer_id: Optional[UUID] = None
    currency_id: Optional[str] = None
    status: Optional[str] = None


@dataclass(frozen=True)
class CancelOrder:
    order_id: UUID
    reason: Optional[str] = None