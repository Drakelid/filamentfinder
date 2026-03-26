from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, JSON, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models import Base

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.price_observation import PriceObservation
    from app.models.price_change import PriceChange
    from app.models.price_alert import PriceAlert


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    variant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    gtin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latest_change_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    latest_change_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    latest_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    raw_data_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    canonical_product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    source: Mapped["Source"] = relationship("Source", back_populates="products")
    price_observations: Mapped[List["PriceObservation"]] = relationship(
        "PriceObservation", back_populates="product", cascade="all, delete-orphan"
    )
    price_changes: Mapped[List["PriceChange"]] = relationship(
        "PriceChange", back_populates="product", cascade="all, delete-orphan"
    )
    price_alerts: Mapped[List["PriceAlert"]] = relationship(
        "PriceAlert", back_populates="product", cascade="all, delete-orphan"
    )
    canonical_product: Mapped[Optional["Product"]] = relationship(
        "Product", remote_side=[id], foreign_keys=[canonical_product_id]
    )

    @property
    def latest_price(self) -> Optional["PriceObservation"]:
        if self.price_observations:
            return max(self.price_observations, key=lambda p: p.observed_at)
        return None
