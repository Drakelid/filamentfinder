from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, JSON, Text, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.crawl_run import CrawlRun


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
    shipping_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    robots_txt_allowed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    failure_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="source", cascade="all, delete-orphan"
    )
    crawl_runs: Mapped[List["CrawlRun"]] = relationship(
        "CrawlRun", back_populates="source", cascade="all, delete-orphan"
    )

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
