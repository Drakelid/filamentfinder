from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class LatestPriceResponse(BaseModel):
    price_amount: Optional[Decimal]
    currency: Optional[str]
    list_price_amount: Optional[Decimal]
    shipping_amount: Optional[Decimal]
    shipping_currency: Optional[str]
    total_price_amount: Optional[Decimal]
    in_stock: Optional[bool]
    observed_at: datetime

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    id: int
    source_id: int
    canonical_url: str
    name: str
    brand: Optional[str]
    category: str
    product_type: Optional[str]
    variant: Optional[str]
    color: Optional[str]
    size: Optional[str]
    image_url: Optional[str]
    sku: Optional[str]
    gtin: Optional[str]
    active: bool
    confidence: float
    latest_change_percent: Optional[float] = None
    latest_change_type: Optional[str] = None
    latest_change_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime]
    latest_price: Optional[LatestPriceResponse] = None
    price_per_kg: Optional[float] = None

    class Config:
        from_attributes = True


class ProductDetailResponse(ProductResponse):
    source_name: Optional[str] = None
    source_domain: str = ""
    canonical_product_id: Optional[int] = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
