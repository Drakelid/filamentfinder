import base64
import os
from typing import Optional
from urllib.parse import urlsplit, urlunsplit
from pydantic import field_validator
from pydantic_settings import BaseSettings
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


class Settings(BaseSettings):
    database_url: str = "postgresql://filamentfinder:filamentfinder@localhost:5432/filamentfinder"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = False
    admin_api_key: Optional[str] = None
    config_encryption_key: Optional[str] = None
    
    crawler_user_agent: str = "FilamentFinder/1.0 (+https://github.com/filamentfinder; bot)"
    crawler_rate_limit: float = 1.0
    crawler_max_pages: int = 100
    crawler_max_depth: int = 3
    crawler_timeout: int = 30
    crawler_respect_robots_txt: bool = True
    
    scan_schedule_enabled: bool = True
    scan_schedule_cron: str = "0 6 * * *"
    
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    notification_email: Optional[str] = None
    
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return False

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def _normalize_service_urls(cls, value):
        if isinstance(value, str):
            return _normalize_container_service_urls(value)
        return value

    def get_cors_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",")]
        return [origin for origin in origins if origin]

    def get_config_encryption_key(self) -> str:
        """Return a valid Fernet key or a safe debug fallback."""
        key = (self.config_encryption_key or "").strip()
        if key and len(key) == 44:
            return key

        if self.debug:
            return base64.urlsafe_b64encode(
                b"0123456789abcdef0123456789abcdef"
            ).decode()

        raise RuntimeError(
            "CONFIG_ENCRYPTION_KEY must be set to a valid 44-character Fernet key when DEBUG is false"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
