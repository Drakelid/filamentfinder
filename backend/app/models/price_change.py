from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Numeric, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models import Base

if TYPE_CHECKING:
    from app.models.product import Product


class PriceChange(Base):
    __tablename__ = "price_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    old_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    old_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    new_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    change_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="price_changes")
