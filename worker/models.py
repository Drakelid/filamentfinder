from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import String, Boolean, DateTime, JSON, Text, Integer, ForeignKey, Numeric, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from worker.database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    crawl_rules_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    selector_overrides_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    shipping_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    retry_policy_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    crawl_duration_stats_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    alert_settings_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    shipping_fee: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    robots_txt_allowed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    failure_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    products: Mapped[List["Product"]] = relationship("Product", back_populates="source")
    crawl_runs: Mapped[List["CrawlRun"]] = relationship("CrawlRun", back_populates="source")

    @property
    def crawl_rules(self) -> dict:
        defaults = {
            "max_pages": 100,
            "max_depth": 3,
            "same_domain_only": True,
            "url_patterns": [],
            "exclude_patterns": [],
            "respect_robots_txt": True,
        }
        if self.crawl_rules_json:
            defaults.update(self.crawl_rules_json)
        return defaults

    @property
    def selector_overrides(self) -> dict:
        return self.selector_overrides_json or {}

    @property
    def shipping_profile(self) -> dict:
        return self.shipping_profile_json or {}

    @property
    def retry_policy(self) -> dict:
        defaults = {
            "max_retries": 3,
            "backoff_seconds": 300,
            "retry_statuses": ["failed"],
        }
        if self.retry_policy_json:
            defaults.update(self.retry_policy_json)
        return defaults

    @property
    def alert_settings(self) -> dict:
        defaults = {
            "failure_threshold": 3,
            "stale_hours": 24,
            "notify_webhook": False,
            "notify_email": False,
        }
        if self.alert_settings_json:
            defaults.update(self.alert_settings_json)
        return defaults

    @property
    def crawl_duration_stats(self) -> dict:
        return self.crawl_duration_stats_json or {}


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), index=True)
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
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_data_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    canonical_product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    source: Mapped["Source"] = relationship("Source", back_populates="products")
    price_observations: Mapped[List["PriceObservation"]] = relationship("PriceObservation", back_populates="product")
    price_changes: Mapped[List["PriceChange"]] = relationship("PriceChange", back_populates="product")
    price_alerts: Mapped[List["PriceAlert"]] = relationship("PriceAlert", back_populates="product")


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
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


class PriceChange(Base):
    __tablename__ = "price_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    old_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    old_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    new_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    change_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="price_changes")


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="price_alerts")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    pages_visited: Mapped[int] = mapped_column(Integer, default=0)
    products_found: Mapped[int] = mapped_column(Integer, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, default=0)
    price_changes_detected: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    error_messages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    stats_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    source: Mapped["Source"] = relationship("Source", back_populates="crawl_runs")
