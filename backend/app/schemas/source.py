from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field


class CrawlRules(BaseModel):
    max_pages: int = Field(default=100, ge=1, le=10000)
    max_depth: int = Field(default=3, ge=1, le=10)
    same_domain_only: bool = True
    url_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)
    respect_robots_txt: bool = True
    schedule_start_hour: Optional[str] = Field(
        default=None,
        pattern=r"^([01]?\d|2[0-3]):[0-5]\d$",
        description="24h HH:MM start time in source timezone",
    )
    schedule_end_hour: Optional[str] = Field(
        default=None,
        pattern=r"^([01]?\d|2[0-3]):[0-5]\d$",
        description="24h HH:MM end time in source timezone",
    )
    schedule_timezone: Optional[str] = Field(default=None, description="IANA timezone name")
    schedule_days: List[str] = Field(
        default_factory=list,
        description="List of allowed weekday identifiers e.g. ['mon','tue']",
    )


class SelectorOverrides(BaseModel):
    product_name: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    image: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    in_stock: Optional[str] = None
    product_links: Optional[str] = None


class RetryPolicy(BaseModel):
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_seconds: int = Field(default=300, ge=0, le=86400)
    retry_statuses: List[str] = Field(default_factory=lambda: ['failed'])


class CrawlDurationStats(BaseModel):
    avg_seconds: Optional[float] = Field(default=None, ge=0)
    p95_seconds: Optional[float] = Field(default=None, ge=0)
    last_seconds: Optional[float] = Field(default=None, ge=0)


class AlertSettings(BaseModel):
    failure_threshold: int = Field(default=3, ge=1, le=20)
    stale_hours: int = Field(default=24, ge=1, le=168)
    notify_webhook: bool = False
    notify_email: bool = False


class SourceCreate(BaseModel):
    url: str
    name: Optional[str] = None
    crawl_rules: Optional[CrawlRules] = None
    selector_overrides: Optional[SelectorOverrides] = None
    shipping_fee: Optional[Decimal] = None
    retry_policy: Optional[RetryPolicy] = None
    alert_settings: Optional[AlertSettings] = None


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    crawl_rules: Optional[CrawlRules] = None
    selector_overrides: Optional[SelectorOverrides] = None
    shipping_fee: Optional[Decimal] = None
    retry_policy: Optional[RetryPolicy] = None
    alert_settings: Optional[AlertSettings] = None


class ScrapeStats(BaseModel):
    last_1h: int = 0
    last_12h: int = 0
    last_24h: int = 0


class CrawlRunSummary(BaseModel):
    id: int
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    duration_seconds: Optional[float]
    pages_visited: int
    products_found: int
    products_updated: int
    price_changes_detected: int
    errors_count: int


class SourceResponse(BaseModel):
    id: int
    url: str
    domain: str
    name: Optional[str]
    active: bool
    crawl_rules: CrawlRules
    selector_overrides: Optional[SelectorOverrides]
    shipping_fee: Optional[Decimal]
    robots_txt_allowed: Optional[bool]
    retry_policy: Optional[RetryPolicy]
    crawl_duration_stats: Optional[CrawlDurationStats]
    alert_settings: Optional[AlertSettings]
    created_at: datetime
    updated_at: datetime
    last_scan_at: Optional[datetime]
    status: str
    status_message: Optional[str]
    failure_streak: int = 0
    next_retry_at: Optional[datetime] = None
    product_count: int = 0
    scrape_stats: ScrapeStats = Field(default_factory=ScrapeStats)
    latest_run: Optional[CrawlRunSummary] = None
    success_rate_24h: Optional[float] = None

    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    items: List[SourceResponse]
    total: int
