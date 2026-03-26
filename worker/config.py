import os
from typing import Optional
from urllib.parse import urlsplit, urlunsplit
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


def _rewrite_service_hostname(url: str, service_name: str, ip_address: str) -> str:
    if not url:
        return url

    parts = urlsplit(url)
    if parts.hostname != service_name:
        return url

    netloc = ip_address
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials = f"{credentials}:{parts.password}"
        netloc = f"{credentials}@{netloc}"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _normalize_container_service_urls(url: str) -> str:
    if os.environ.get("GLUETUN_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return url

    normalized = _rewrite_service_hostname(url, "db", "172.30.0.3")
    normalized = _rewrite_service_hostname(normalized, "redis", "172.30.0.4")
    return normalized


class WorkerSettings(BaseSettings):
    database_url: str = "postgresql://filamentfinder:filamentfinder@localhost:5432/filamentfinder"
    redis_url: str = "redis://localhost:6379/0"
    
    crawler_user_agent: str = "FilamentFinder/1.0 (+https://github.com/filamentfinder; bot)"
    crawler_rate_limit: float = 0.5  # Max 0.5 requests per second (2 seconds between requests)
    crawler_min_delay: float = 2.0  # Minimum delay between requests in seconds
    crawler_max_delay: float = 5.0  # Maximum delay for random jitter
    crawler_max_pages: int = 100
    crawler_max_depth: int = 3
    crawler_timeout: int = 30
    crawler_respect_robots_txt: bool = True
    crawler_concurrent_requests: int = 1  # Only 1 concurrent request per domain
    crawler_max_concurrent_sources: int = 6  # Max number of sources to crawl simultaneously
    
    scan_schedule_enabled: bool = True
    scan_schedule_cron: str = "0 6 * * *"
    
    price_check_enabled: bool = True
    price_check_interval_hours: int = 48  # Check prices every 48 hours
    price_check_batch_size: int = 50  # Number of products to check per batch
    
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    notification_email: Optional[str] = None
    
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None

    mullvad_socks_proxy: Optional[str] = None
    
    log_level: str = "INFO"

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def _normalize_service_urls(cls, value):
        if isinstance(value, str):
            return _normalize_container_service_urls(value)
        return value

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> WorkerSettings:
    return WorkerSettings()
