from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, JSON, Integer, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models import Base

if TYPE_CHECKING:
    from app.models.product import Product


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    price_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    list_price_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    shipping_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    shipping_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    total_price_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    in_stock: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    stock_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    crawl_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="price_observations")
