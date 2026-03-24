from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class PriceObservationResponse(BaseModel):
    id: int
    product_id: int
    observed_at: datetime
    price_amount: Optional[Decimal]
    currency: Optional[str]
    list_price_amount: Optional[Decimal]
    shipping_amount: Optional[Decimal]
    shipping_currency: Optional[str]
    total_price_amount: Optional[Decimal]
    in_stock: Optional[bool]
    stock_quantity: Optional[int]

    class Config:
        from_attributes = True


class PriceChangeResponse(BaseModel):
    id: int
    product_id: int
    changed_at: datetime
    old_price: Optional[Decimal]
    new_price: Optional[Decimal]
    old_currency: Optional[str]
    new_currency: Optional[str]
    change_type: str
    change_percent: Optional[float]
    note: Optional[str]

    class Config:
        from_attributes = True


class PriceHistoryResponse(BaseModel):
    observations: List[PriceObservationResponse]
    changes: List[PriceChangeResponse]
    total_observations: int
    total_changes: int
