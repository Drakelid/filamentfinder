from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class PriceAlertCreate(BaseModel):
    product_id: int
    target_price: Decimal
    currency: str


class PriceAlertRead(BaseModel):
    id: UUID
    product_id: int
    target_price: Decimal
    currency: str
    active: bool
    created_at: datetime
    triggered_at: Optional[datetime]

    class Config:
        from_attributes = True


class PriceAlertList(BaseModel):
    items: List[PriceAlertRead]
    total: int
