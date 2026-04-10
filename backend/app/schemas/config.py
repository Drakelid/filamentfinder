from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.schemas.source import CrawlRules, SelectorOverrides


class ConfigBase(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None


class ConfigCreate(ConfigBase):
    pass


class ConfigUpdate(BaseModel):
    value: Optional[str] = None


class ConfigResponse(ConfigBase):
    id: int
    encrypted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VPNConfigUpdate(BaseModel):
    """Schema for updating VPN configuration."""
    account_number: Optional[str] = None
    socks_proxy: Optional[str] = None
    enabled: bool = False
    auto_rotate: bool = True
    rotate_interval_minutes: int = 30


class VPNConfigResponse(BaseModel):
    """Schema for VPN configuration response."""
    gluetun_mode: bool = False
    account_number_set: bool
    proxy_configured: bool
    wireguard_file_configured: bool = False
    wireguard_file_name: Optional[str] = None
    wireguard_uploaded_at: Optional[datetime] = None
    wireguard_profile_count: int = 0
    wireguard_active_file_name: Optional[str] = None
    enabled: bool
    auto_rotate: bool
    rotate_interval_minutes: int
    connected: bool
    current_server: Optional[str] = None
    current_ip: Optional[str] = None


class VPNStatusResponse(BaseModel):
    """Schema for VPN status response."""
    connected: bool
    ip: Optional[str] = None
    country: Optional[str] = None
    mullvad_exit_ip: bool = False
    error: Optional[str] = None


class WireGuardConfigUploadResponse(BaseModel):
    file_names: list[str]
    active_file_name: str
    profile_count: int
    restarted: bool
    restart_error: Optional[str] = None


class CrawlerConfigResponse(BaseModel):
    user_agent: str
    rate_limit: float
    min_delay: float
    max_delay: float
    max_pages: int
    max_depth: int
    timeout: int
    respect_robots_txt: bool
    concurrent_requests: int
    max_concurrent_sources: int
    scan_schedule_enabled: bool
    scan_schedule_cron: str
    price_check_enabled: bool
    price_check_interval_hours: int
    price_check_batch_size: int
    js_domains: str


class CrawlerConfigUpdate(BaseModel):
    user_agent: str = Field(min_length=1, max_length=512)
    rate_limit: float = Field(ge=0)
    min_delay: float = Field(ge=0)
    max_delay: float = Field(ge=0)
    max_pages: int = Field(ge=1, le=10000)
    max_depth: int = Field(ge=0, le=20)
    timeout: int = Field(ge=1, le=600)
    respect_robots_txt: bool
    concurrent_requests: int = Field(ge=1, le=50)
    max_concurrent_sources: int = Field(ge=1, le=100)
    scan_schedule_enabled: bool
    scan_schedule_cron: str = Field(min_length=5, max_length=128)
    price_check_enabled: bool
    price_check_interval_hours: int = Field(ge=1, le=720)
    price_check_batch_size: int = Field(ge=1, le=10000)
    js_domains: str = Field(default="", max_length=4096)


class NotificationConfigResponse(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: int
    smtp_user: Optional[str] = None
    smtp_from: Optional[str] = None
    notification_email: Optional[str] = None
    webhook_url: Optional[str] = None
    smtp_password_set: bool = False
    webhook_secret_set: bool = False


class NotificationConfigUpdate(BaseModel):
    smtp_host: Optional[str] = Field(default=None, max_length=255)
    smtp_port: int = Field(ge=1, le=65535)
    smtp_user: Optional[str] = Field(default=None, max_length=255)
    smtp_password: Optional[str] = Field(default=None, max_length=512)
    smtp_from: Optional[str] = Field(default=None, max_length=255)
    notification_email: Optional[str] = Field(default=None, max_length=255)
    webhook_url: Optional[str] = Field(default=None, max_length=2048)
    webhook_secret: Optional[str] = Field(default=None, max_length=512)


class ScrapeTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parser: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1500)
    detection_signals: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    crawl_rules: CrawlRules = Field(default_factory=CrawlRules)
    selector_overrides: Optional[SelectorOverrides] = None


class ScrapeTemplateCreate(ScrapeTemplateBase):
    pass


class ScrapeTemplateUpdate(ScrapeTemplateBase):
    pass


class ScrapeTemplateResponse(ScrapeTemplateBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ScrapeTemplateListResponse(BaseModel):
    items: list[ScrapeTemplateResponse]
