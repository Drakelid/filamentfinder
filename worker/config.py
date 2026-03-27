import os
from typing import Optional
from sqlalchemy import create_engine, text
from pydantic_settings import BaseSettings
from pydantic import field_validator
from cryptography.fernet import Fernet, InvalidToken

from shared.network import normalize_container_service_urls as _normalize_container_service_urls


DB_CONFIG_CASTERS = {
    "crawler_js_domains": str,
    "crawler_user_agent": str,
    "crawler_rate_limit": float,
    "crawler_min_delay": float,
    "crawler_max_delay": float,
    "crawler_max_pages": int,
    "crawler_max_depth": int,
    "crawler_timeout": int,
    "crawler_respect_robots_txt": bool,
    "crawler_concurrent_requests": int,
    "crawler_max_concurrent_sources": int,
    "scan_schedule_enabled": bool,
    "scan_schedule_cron": str,
    "price_check_enabled": bool,
    "price_check_interval_hours": int,
    "price_check_batch_size": int,
    "price_change_min_percent": float,
    "smtp_host": str,
    "smtp_port": int,
    "smtp_user": str,
    "smtp_password": str,
    "smtp_from": str,
    "notification_email": str,
    "webhook_url": str,
    "webhook_secret": str,
}
LEGACY_CRAWLER_USER_AGENT = "FilamentFinder/1.0 (+https://github.com/filamentfinder; bot)"
DEFAULT_BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"


class WorkerSettings(BaseSettings):
    database_url: str = "postgresql://filamentfinder:filamentfinder@localhost:5432/filamentfinder"
    redis_url: str = "redis://localhost:6379/0"
    
    crawler_js_domains: str = ""   # Extra comma-separated domains that need Playwright, beyond the hardcoded list
    crawler_user_agent: str = DEFAULT_BROWSER_USER_AGENT
    crawler_rate_limit: float = 0.5  # Max 0.5 requests per second (2 seconds between requests)
    crawler_min_delay: float = 2.0  # Minimum delay between requests in seconds
    crawler_max_delay: float = 5.0  # Maximum delay for random jitter
    crawler_max_pages: int = 300
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
    price_change_min_percent: float = 1.0  # Ignore changes below this percent threshold
    
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

def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _coerce_config_value(value: object, caster: type):
    if caster is bool:
        return _parse_bool(value)
    if caster is int:
        return int(str(value).strip())
    if caster is float:
        return float(str(value).strip())
    return str(value)


def _normalize_crawler_user_agent(value: object) -> str:
    normalized = str(value).strip()
    if not normalized or normalized == LEGACY_CRAWLER_USER_AGENT:
        return DEFAULT_BROWSER_USER_AGENT
    return normalized


def _get_fernet() -> Fernet | None:
    encryption_key = (os.environ.get("CONFIG_ENCRYPTION_KEY") or "").strip()
    if not encryption_key:
        return None
    try:
        return Fernet(encryption_key.encode())
    except Exception:
        return None


def _decrypt_if_needed(value: object, encrypted: bool) -> str:
    if value is None:
        return ""
    if not encrypted:
        return str(value)
    fernet = _get_fernet()
    if fernet is None:
        return ""
    try:
        return fernet.decrypt(str(value).encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return ""


def _load_db_overrides(settings: WorkerSettings) -> dict[str, object]:
    keys = tuple(DB_CONFIG_CASTERS.keys())
    placeholders = ", ".join(f":key_{index}" for index, _ in enumerate(keys))
    params = {f"key_{index}": key for index, key in enumerate(keys)}
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(f"SELECT key, value, encrypted FROM config WHERE key IN ({placeholders})"),
                params,
            )
            overrides: dict[str, object] = {}
            for key, raw_value, encrypted in rows:
                if raw_value is None:
                    continue
                caster = DB_CONFIG_CASTERS.get(key)
                if caster is None:
                    continue
                try:
                    decoded_value = _decrypt_if_needed(raw_value, bool(encrypted))
                    if decoded_value == "" and caster is not str:
                        continue
                    coerced = _coerce_config_value(decoded_value, caster)
                    if key == "crawler_user_agent":
                        coerced = _normalize_crawler_user_agent(coerced)
                    overrides[key] = coerced
                except (TypeError, ValueError):
                    continue
            return overrides
    except Exception:
        return {}
    finally:
        engine.dispose()


_settings: WorkerSettings | None = None


def _ensure_settings() -> WorkerSettings:
    global _settings
    if _settings is None:
        _settings = WorkerSettings()
        refresh_settings()
    return _settings


def refresh_settings() -> WorkerSettings:
    global _settings
    settings = _settings if _settings is not None else WorkerSettings()
    overrides = _load_db_overrides(settings)
    for key in DB_CONFIG_CASTERS:
        if key in overrides:
            setattr(settings, key, overrides[key])
    _settings = settings
    return settings


def get_settings() -> WorkerSettings:
    return _ensure_settings()
