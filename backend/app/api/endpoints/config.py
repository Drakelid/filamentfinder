import json
import os
import re
import shutil
import socket
import ipaddress
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import urlparse
from uuid import uuid4

import docker
import httpx
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import require_admin_api_key
from app.models.config import Config
from app.schemas.config import (
    ConfigResponse,
    ConfigUpdate,
    CrawlerConfigResponse,
    CrawlerConfigUpdate,
    NotificationConfigResponse,
    NotificationConfigUpdate,
    ScrapeTemplateCreate,
    ScrapeTemplateListResponse,
    ScrapeTemplateResponse,
    ScrapeTemplateUpdate,
    VPNConfigUpdate,
    VPNConfigResponse,
    VPNStatusResponse,
    WireGuardConfigUploadResponse,
)

router = APIRouter(dependencies=[Depends(require_admin_api_key)])
GLUETUN_WIREGUARD_DIR = Path("/gluetun/wireguard")
GLUETUN_WIREGUARD_FILE = GLUETUN_WIREGUARD_DIR / "wg0.conf"
GLUETUN_WIREGUARD_PROFILES_DIR = GLUETUN_WIREGUARD_DIR / "profiles"
WIREGUARD_PRIVATE_KEY_PATTERN = re.compile(r"^\s*PrivateKey\s*=\s*(.+?)\s*$", re.MULTILINE)
WIREGUARD_ADDRESS_PATTERN = re.compile(r"^\s*Address\s*=\s*(.+?)\s*$", re.MULTILINE)
WIREGUARD_ENDPOINT_PATTERN = re.compile(r"^(\s*Endpoint\s*=\s*)([^:\s]+)(:\d+\s*)$", re.MULTILINE)
CRAWLER_CONFIG_DESCRIPTIONS = {
    "crawler_user_agent": "Crawler user agent",
    "crawler_rate_limit": "Crawler requests per second target",
    "crawler_min_delay": "Crawler minimum delay between requests in seconds",
    "crawler_max_delay": "Crawler maximum delay between requests in seconds",
    "crawler_max_pages": "Crawler maximum pages per source run",
    "crawler_max_depth": "Crawler maximum link depth per source run",
    "crawler_timeout": "Crawler HTTP timeout in seconds",
    "crawler_respect_robots_txt": "Whether the crawler respects robots.txt",
    "crawler_concurrent_requests": "Crawler concurrent requests per domain",
    "crawler_max_concurrent_sources": "Maximum sources crawled simultaneously",
    "scan_schedule_enabled": "Whether scheduled scans are enabled",
    "scan_schedule_cron": "Scheduled scan cron expression",
    "price_check_enabled": "Whether periodic product price checks are enabled",
    "price_check_interval_hours": "Hours between product price checks",
    "price_check_batch_size": "Batch size for periodic product price checks",
    "crawler_js_domains": "Extra comma-separated domains that require Playwright browser rendering",
}
NOTIFICATION_CONFIG_DESCRIPTIONS = {
    "smtp_host": "SMTP host for outbound email notifications",
    "smtp_port": "SMTP port for outbound email notifications",
    "smtp_user": "SMTP username for outbound email notifications",
    "smtp_password": "SMTP password for outbound email notifications",
    "smtp_from": "From address for outbound email notifications",
    "notification_email": "Destination email address for FilamentFinder notifications",
    "webhook_url": "Webhook destination URL for notifications",
    "webhook_secret": "Shared secret used to sign notification webhooks",
}
LEGACY_CRAWLER_USER_AGENT = "FilamentFinder/1.0 (+https://github.com/filamentfinder; bot)"
DEFAULT_BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
SCRAPE_TEMPLATES_CONFIG_KEY = "scrape_templates_json"
SCRAPE_TEMPLATES_DESCRIPTION = "User-defined scraping templates"


@lru_cache()
def get_fernet():
    """Get Fernet instance for encryption/decryption."""
    settings = get_settings()
    return Fernet(settings.get_config_encryption_key().encode())


def encrypt_value(value: str) -> str:
    """Encrypt a value."""
    if not value:
        return ""
    f = get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decrypt a value."""
    if not value:
        return ""
    f = get_fernet()
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        return ""


def get_config_value(db: Session, key: str, default: str = "") -> str:
    """Get a configuration value by key."""
    config = db.query(Config).filter(Config.key == key).first()
    if not config:
        return default
    if config.encrypted:
        return decrypt_value(config.value)
    return config.value or default


def set_config_value(db: Session, key: str, value: str, encrypted: bool = False, description: str = None):
    """Set a configuration value."""
    config = db.query(Config).filter(Config.key == key).first()
    
    stored_value = encrypt_value(value) if encrypted else value
    
    if config:
        config.value = stored_value
        config.encrypted = encrypted
        if description:
            config.description = description
    else:
        config = Config(
            key=key,
            value=stored_value,
            encrypted=encrypted,
            description=description,
        )
        db.add(config)
    
    db.commit()
    return config


def get_proxy_host(proxy_url: str) -> str | None:
    if not proxy_url:
        return None
    try:
        parsed = urlparse(proxy_url)
        return parsed.hostname
    except Exception:
        return None


def get_gluetun_proxy_url() -> str:
    proxy_url = os.environ.get("MULLVAD_SOCKS_PROXY", "").strip()
    if proxy_url and get_proxy_host(proxy_url) == "gluetun":
        gluetun_ip = get_gluetun_container_ip()
        if gluetun_ip:
            return proxy_url.replace("gluetun", gluetun_ip, 1)
        return proxy_url
    gluetun_ip = get_gluetun_container_ip()
    if gluetun_ip:
        return f"http://{gluetun_ip}:8888"
    return "http://gluetun:8888"


def parse_wireguard_config(config_text: str) -> tuple[str, str]:
    private_key_match = WIREGUARD_PRIVATE_KEY_PATTERN.search(config_text)
    address_match = WIREGUARD_ADDRESS_PATTERN.search(config_text)
    if not private_key_match or not address_match:
        raise HTTPException(status_code=400, detail="WireGuard config must contain PrivateKey and Address fields")

    private_key = private_key_match.group(1).strip()
    addresses = address_match.group(1).strip()
    if not private_key or not addresses:
        raise HTTPException(status_code=400, detail="WireGuard config contains empty PrivateKey or Address values")

    return private_key, addresses


def normalize_wireguard_config(config_text: str) -> str:
    def replace_address(match: re.Match[str]) -> str:
        addresses = [part.strip() for part in match.group(1).split(",") if part.strip()]
        ipv4_addresses: list[str] = []
        for address in addresses:
            interface = ipaddress.ip_interface(address)
            if interface.version == 4:
                ipv4_addresses.append(address)

        if not ipv4_addresses:
            raise HTTPException(status_code=400, detail="WireGuard config must contain at least one IPv4 interface address")

        return f"Address = {', '.join(ipv4_addresses)}"

    def replace_endpoint(match: re.Match[str]) -> str:
        prefix, host, suffix = match.groups()
        try:
            ipaddress.ip_address(host)
            return match.group(0)
        except ValueError:
            pass

        try:
            resolved_ip = socket.gethostbyname(host)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"Failed to resolve WireGuard endpoint host {host}: {exc}") from exc

        return f"{prefix}{resolved_ip}{suffix}"

    normalized = WIREGUARD_ADDRESS_PATTERN.sub(lambda match: replace_address(match), config_text)
    normalized = WIREGUARD_ENDPOINT_PATTERN.sub(replace_endpoint, normalized)
    return normalized


def sanitize_wireguard_filename(filename: str) -> str:
    sanitized = Path(filename).name.strip()
    if not sanitized or sanitized in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid WireGuard config filename")
    if not sanitized.lower().endswith(".conf"):
        raise HTTPException(status_code=400, detail="WireGuard config must use the .conf extension")
    return sanitized


def load_wireguard_profiles(db: Session) -> list[dict]:
    raw = get_config_value(db, "vpn_wireguard_profiles_json", "[]")
    try:
        profiles = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(profiles, list):
        return []
    return [profile for profile in profiles if isinstance(profile, dict) and profile.get("file_name")]


def save_wireguard_profiles(db: Session, profiles: list[dict]):
    set_config_value(
        db,
        "vpn_wireguard_profiles_json",
        json.dumps(profiles),
        description="Uploaded WireGuard profiles",
    )


def get_active_wireguard_file_name(db: Session) -> str | None:
    value = get_config_value(db, "vpn_wireguard_active_file_name", "")
    return value or None


def write_active_wireguard_profile(file_name: str):
    profile_path = GLUETUN_WIREGUARD_PROFILES_DIR / file_name
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"WireGuard profile {file_name} not found")
    GLUETUN_WIREGUARD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(profile_path, GLUETUN_WIREGUARD_FILE)


def restart_gluetun_container() -> str | None:
    try:
        client = docker.from_env()
        project_name = None
        current_container_id = os.environ.get("HOSTNAME")
        if current_container_id:
          try:
              current_container = client.containers.get(current_container_id)
              project_name = current_container.labels.get("com.docker.compose.project")
          except Exception:
              project_name = None

        filters = {"label": ["com.docker.compose.service=gluetun"]}
        if project_name:
            filters["label"].append(f"com.docker.compose.project={project_name}")

        containers = client.containers.list(all=True, filters=filters)
        if not containers:
            return "Gluetun container was not found through the Docker socket"
        containers[0].restart(timeout=10)
        return None
    except Exception as exc:
        return str(exc)


def get_gluetun_container():
    try:
        client = docker.from_env()
        project_name = None
        current_container_id = os.environ.get("HOSTNAME")
        if current_container_id:
            try:
                current_container = client.containers.get(current_container_id)
                project_name = current_container.labels.get("com.docker.compose.project")
            except Exception:
                project_name = None

        filters = {"label": ["com.docker.compose.service=gluetun"]}
        if project_name:
            filters["label"].append(f"com.docker.compose.project={project_name}")

        containers = client.containers.list(all=True, filters=filters)
        if not containers:
            return None
        return containers[0]
    except Exception:
        return None


def get_gluetun_container_ip() -> str | None:
    container = get_gluetun_container()
    if not container:
        return None
    try:
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        for network in networks.values():
            ip_address = network.get("IPAddress")
            if ip_address:
                return ip_address
    except Exception:
        return None
    return None


def get_gluetun_control_base_url() -> str:
    gluetun_ip = get_gluetun_container_ip()
    if gluetun_ip:
        return f"http://{gluetun_ip}:8000"
    return "http://gluetun:8000"


def proxy_targets_gluetun(proxy_url: str) -> bool:
    proxy_host = get_proxy_host(proxy_url)
    if proxy_host == "gluetun":
        return True
    gluetun_ip = get_gluetun_container_ip()
    return bool(gluetun_ip and proxy_host == gluetun_ip)


def get_wireguard_file_metadata(db: Session) -> tuple[bool, str | None, datetime | None, int, str | None]:
    profiles = load_wireguard_profiles(db)
    if not GLUETUN_WIREGUARD_FILE.exists() and not profiles:
        return False, None, None, 0, None

    file_name = get_config_value(db, "vpn_wireguard_file_name", "") or GLUETUN_WIREGUARD_FILE.name
    uploaded_at_raw = get_config_value(db, "vpn_wireguard_uploaded_at", "")
    uploaded_at = None
    if uploaded_at_raw:
        try:
            uploaded_at = datetime.fromisoformat(uploaded_at_raw)
        except ValueError:
            uploaded_at = None

    return True, file_name, uploaded_at, len(profiles), get_active_wireguard_file_name(db)


def get_effective_proxy_url(db: Session) -> str:
    configured_proxy = get_config_value(db, "mullvad_socks_proxy", "").strip()
    env_proxy = os.environ.get("MULLVAD_SOCKS_PROXY", "").strip()
    wireguard_file_configured, _, _, wireguard_profile_count, _ = get_wireguard_file_metadata(db)

    if wireguard_file_configured or wireguard_profile_count > 0:
        return get_gluetun_proxy_url()

    return configured_proxy or env_proxy


def _parse_bool(value: str | bool | None, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip()) if value is not None and str(value).strip() else default
    except (TypeError, ValueError):
        return default


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(str(value).strip()) if value is not None and str(value).strip() else default
    except (TypeError, ValueError):
        return default


def _serialize_bool(value: bool) -> str:
    return "true" if value else "false"


def _normalize_crawler_user_agent(value: str | None, default: str) -> str:
    normalized = (value or "").strip()
    if not normalized or normalized == LEGACY_CRAWLER_USER_AGENT:
        return default
    return normalized


def get_crawler_config_payload(db: Session) -> CrawlerConfigResponse:
    settings = get_settings()
    raw_user_agent = get_config_value(db, "crawler_user_agent", settings.crawler_user_agent)
    user_agent = _normalize_crawler_user_agent(raw_user_agent, settings.crawler_user_agent)
    if user_agent != (raw_user_agent or "").strip():
        set_config_value(db, "crawler_user_agent", user_agent, description=CRAWLER_CONFIG_DESCRIPTIONS.get("crawler_user_agent"))
    return CrawlerConfigResponse(
        user_agent=user_agent,
        rate_limit=_parse_float(get_config_value(db, "crawler_rate_limit", str(settings.crawler_rate_limit)), settings.crawler_rate_limit),
        min_delay=_parse_float(get_config_value(db, "crawler_min_delay", "2.0"), 2.0),
        max_delay=_parse_float(get_config_value(db, "crawler_max_delay", "5.0"), 5.0),
        max_pages=_parse_int(get_config_value(db, "crawler_max_pages", str(settings.crawler_max_pages)), settings.crawler_max_pages),
        max_depth=_parse_int(get_config_value(db, "crawler_max_depth", str(settings.crawler_max_depth)), settings.crawler_max_depth),
        timeout=_parse_int(get_config_value(db, "crawler_timeout", str(settings.crawler_timeout)), settings.crawler_timeout),
        respect_robots_txt=_parse_bool(
            get_config_value(db, "crawler_respect_robots_txt", _serialize_bool(settings.crawler_respect_robots_txt)),
            settings.crawler_respect_robots_txt,
        ),
        concurrent_requests=_parse_int(get_config_value(db, "crawler_concurrent_requests", "1"), 1),
        max_concurrent_sources=_parse_int(get_config_value(db, "crawler_max_concurrent_sources", "6"), 6),
        scan_schedule_enabled=_parse_bool(
            get_config_value(db, "scan_schedule_enabled", _serialize_bool(settings.scan_schedule_enabled)),
            settings.scan_schedule_enabled,
        ),
        scan_schedule_cron=get_config_value(db, "scan_schedule_cron", settings.scan_schedule_cron) or settings.scan_schedule_cron,
        price_check_enabled=_parse_bool(get_config_value(db, "price_check_enabled", "true"), True),
        price_check_interval_hours=_parse_int(get_config_value(db, "price_check_interval_hours", "48"), 48),
        price_check_batch_size=_parse_int(get_config_value(db, "price_check_batch_size", "50"), 50),
        js_domains=get_config_value(db, "crawler_js_domains", "") or "",
    )


def get_notification_config_payload(db: Session) -> NotificationConfigResponse:
    settings = get_settings()
    smtp_password = get_config_value(db, "smtp_password", settings.smtp_password or "")
    webhook_secret = get_config_value(db, "webhook_secret", settings.webhook_secret or "")
    return NotificationConfigResponse(
        smtp_host=get_config_value(db, "smtp_host", settings.smtp_host or "") or None,
        smtp_port=_parse_int(get_config_value(db, "smtp_port", str(settings.smtp_port)), settings.smtp_port),
        smtp_user=get_config_value(db, "smtp_user", settings.smtp_user or "") or None,
        smtp_from=get_config_value(db, "smtp_from", settings.smtp_from or "") or None,
        notification_email=get_config_value(db, "notification_email", settings.notification_email or "") or None,
        webhook_url=get_config_value(db, "webhook_url", settings.webhook_url or "") or None,
        smtp_password_set=bool(smtp_password),
        webhook_secret_set=bool(webhook_secret),
    )


def get_scrape_templates_payload(db: Session) -> list[ScrapeTemplateResponse]:
    raw = get_config_value(db, SCRAPE_TEMPLATES_CONFIG_KEY, "[]")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = []

    if not isinstance(payload, list):
        payload = []

    templates: list[ScrapeTemplateResponse] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        try:
            templates.append(ScrapeTemplateResponse(**entry))
        except Exception:
            continue

    templates.sort(key=lambda template: (template.updated_at, template.created_at), reverse=True)
    return templates


def save_scrape_templates_payload(db: Session, templates: list[ScrapeTemplateResponse]):
    serialized = [template.model_dump(mode="json") for template in templates]
    set_config_value(
        db,
        SCRAPE_TEMPLATES_CONFIG_KEY,
        json.dumps(serialized),
        description=SCRAPE_TEMPLATES_DESCRIPTION,
    )


@router.get("/vpn", response_model=VPNConfigResponse)
def get_vpn_config(db: Session = Depends(get_db)):
    """Get VPN configuration."""
    account_number = get_config_value(db, "vpn_account_number", "")
    enabled = get_config_value(db, "vpn_enabled", "false") == "true"
    auto_rotate = get_config_value(db, "vpn_auto_rotate", "true") == "true"
    rotate_interval = int(get_config_value(db, "vpn_rotate_interval_minutes", "30"))
    wireguard_file_configured, wireguard_file_name, wireguard_uploaded_at, wireguard_profile_count, wireguard_active_file_name = get_wireguard_file_metadata(db)
    proxy_url = get_effective_proxy_url(db)
    proxy_host = get_proxy_host(proxy_url)
    gluetun_enabled = wireguard_file_configured or proxy_targets_gluetun(proxy_url)

    connected = enabled and (bool(proxy_url) or gluetun_enabled)
    current_server = None
    if connected:
        if gluetun_enabled:
            current_server = "Gluetun / Mullvad WireGuard"
        elif proxy_host:
            current_server = proxy_host
        else:
            current_server = "SOCKS5 proxy configured"
    current_ip = None

    return VPNConfigResponse(
        gluetun_mode=gluetun_enabled,
        account_number_set=bool(account_number),
        proxy_configured=bool(proxy_url),
        wireguard_file_configured=wireguard_file_configured,
        wireguard_file_name=wireguard_file_name,
        wireguard_uploaded_at=wireguard_uploaded_at,
        wireguard_profile_count=wireguard_profile_count,
        wireguard_active_file_name=wireguard_active_file_name,
        enabled=enabled,
        auto_rotate=auto_rotate,
        rotate_interval_minutes=rotate_interval,
        connected=connected,
        current_server=current_server,
        current_ip=current_ip,
    )


@router.post("/vpn/wireguard-config", response_model=WireGuardConfigUploadResponse)
async def upload_wireguard_config(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload one or more WireGuard config files and restart Gluetun using the active profile."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one WireGuard config file is required")

    profiles = load_wireguard_profiles(db)
    profiles_by_name = {profile["file_name"]: profile for profile in profiles}
    uploaded_names: list[str] = []
    uploaded_at = datetime.now(timezone.utc)

    GLUETUN_WIREGUARD_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="WireGuard config file is required")

        filename = sanitize_wireguard_filename(file.filename)
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail=f"Uploaded WireGuard config {filename} is empty")
        if len(payload) > 64 * 1024:
            raise HTTPException(status_code=400, detail=f"WireGuard config {filename} must be 64 KB or smaller")

        try:
            config_text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"WireGuard config {filename} must be valid UTF-8 text") from exc

        normalized_config_text = normalize_wireguard_config(config_text)
        _, addresses = parse_wireguard_config(normalized_config_text)
        (GLUETUN_WIREGUARD_PROFILES_DIR / filename).write_text(normalized_config_text, encoding="utf-8")
        profiles_by_name[filename] = {
            "file_name": filename,
            "addresses": addresses,
            "uploaded_at": uploaded_at.isoformat(),
        }
        uploaded_names.append(filename)

    profiles = sorted(profiles_by_name.values(), key=lambda profile: profile["file_name"])
    save_wireguard_profiles(db, profiles)

    active_file_name = uploaded_names[0] if uploaded_names else get_active_wireguard_file_name(db)
    if not active_file_name:
        raise HTTPException(status_code=400, detail="No active WireGuard profile is available")

    write_active_wireguard_profile(active_file_name)
    set_config_value(db, "vpn_wireguard_active_file_name", active_file_name, description="Active WireGuard profile")
    set_config_value(db, "vpn_wireguard_file_name", active_file_name, description="Active uploaded WireGuard config filename")
    set_config_value(db, "vpn_wireguard_uploaded_at", uploaded_at.isoformat(), description="Latest uploaded WireGuard config timestamp")

    restart_error = restart_gluetun_container()
    return WireGuardConfigUploadResponse(
        file_names=uploaded_names,
        active_file_name=active_file_name,
        profile_count=len(profiles),
        restarted=restart_error is None,
        restart_error=restart_error,
    )


@router.get("/crawler", response_model=CrawlerConfigResponse)
def get_crawler_config(db: Session = Depends(get_db)):
    """Get crawler configuration."""
    return get_crawler_config_payload(db)


@router.put("/crawler", response_model=CrawlerConfigResponse)
def update_crawler_config(config: CrawlerConfigUpdate, db: Session = Depends(get_db)):
    """Update crawler configuration."""
    values = {
        "crawler_user_agent": _normalize_crawler_user_agent(config.user_agent, DEFAULT_BROWSER_USER_AGENT),
        "crawler_rate_limit": str(config.rate_limit),
        "crawler_min_delay": str(config.min_delay),
        "crawler_max_delay": str(config.max_delay),
        "crawler_max_pages": str(config.max_pages),
        "crawler_max_depth": str(config.max_depth),
        "crawler_timeout": str(config.timeout),
        "crawler_respect_robots_txt": _serialize_bool(config.respect_robots_txt),
        "crawler_concurrent_requests": str(config.concurrent_requests),
        "crawler_max_concurrent_sources": str(config.max_concurrent_sources),
        "scan_schedule_enabled": _serialize_bool(config.scan_schedule_enabled),
        "scan_schedule_cron": config.scan_schedule_cron.strip(),
        "price_check_enabled": _serialize_bool(config.price_check_enabled),
        "price_check_interval_hours": str(config.price_check_interval_hours),
        "price_check_batch_size": str(config.price_check_batch_size),
        "crawler_js_domains": config.js_domains.strip(),
    }

    for key, value in values.items():
        set_config_value(db, key, value, description=CRAWLER_CONFIG_DESCRIPTIONS.get(key))

    return get_crawler_config_payload(db)


@router.get("/notifications", response_model=NotificationConfigResponse)
def get_notification_config(db: Session = Depends(get_db)):
    """Get notification configuration."""
    return get_notification_config_payload(db)


@router.get("/scrape-templates", response_model=ScrapeTemplateListResponse)
def get_scrape_templates(db: Session = Depends(get_db)):
    """Get user-defined scraping templates."""
    return ScrapeTemplateListResponse(items=get_scrape_templates_payload(db))


@router.post("/scrape-templates", response_model=ScrapeTemplateResponse, status_code=201)
def create_scrape_template(template: ScrapeTemplateCreate, db: Session = Depends(get_db)):
    """Create a user-defined scraping template."""
    templates = get_scrape_templates_payload(db)
    now = datetime.now(timezone.utc)
    created = ScrapeTemplateResponse(
        id=str(uuid4()),
        name=template.name,
        parser=template.parser,
        description=template.description,
        detection_signals=template.detection_signals,
        strengths=template.strengths,
        coverage=template.coverage,
        crawl_rules=template.crawl_rules,
        selector_overrides=template.selector_overrides,
        created_at=now,
        updated_at=now,
    )
    templates.append(created)
    save_scrape_templates_payload(db, templates)
    return created


@router.put("/scrape-templates/{template_id}", response_model=ScrapeTemplateResponse)
def update_scrape_template(template_id: str, template: ScrapeTemplateUpdate, db: Session = Depends(get_db)):
    """Update a user-defined scraping template."""
    templates = get_scrape_templates_payload(db)
    for index, existing in enumerate(templates):
        if existing.id != template_id:
            continue

        updated = ScrapeTemplateResponse(
            id=existing.id,
            name=template.name,
            parser=template.parser,
            description=template.description,
            detection_signals=template.detection_signals,
            strengths=template.strengths,
            coverage=template.coverage,
            crawl_rules=template.crawl_rules,
            selector_overrides=template.selector_overrides,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        templates[index] = updated
        save_scrape_templates_payload(db, templates)
        return updated

    raise HTTPException(status_code=404, detail="Scrape template not found")


@router.delete("/scrape-templates/{template_id}", status_code=204)
def delete_scrape_template(template_id: str, db: Session = Depends(get_db)):
    """Delete a user-defined scraping template."""
    templates = get_scrape_templates_payload(db)
    remaining = [template for template in templates if template.id != template_id]
    if len(remaining) == len(templates):
        raise HTTPException(status_code=404, detail="Scrape template not found")

    save_scrape_templates_payload(db, remaining)
    return None


@router.put("/notifications", response_model=NotificationConfigResponse)
def update_notification_config(config: NotificationConfigUpdate, db: Session = Depends(get_db)):
    """Update notification configuration."""
    plain_values = {
        "smtp_host": (config.smtp_host or "").strip(),
        "smtp_port": str(config.smtp_port),
        "smtp_user": (config.smtp_user or "").strip(),
        "smtp_from": (config.smtp_from or "").strip(),
        "notification_email": (config.notification_email or "").strip(),
        "webhook_url": (config.webhook_url or "").strip(),
    }
    secret_values = {
        "smtp_password": config.smtp_password,
        "webhook_secret": config.webhook_secret,
    }

    for key, value in plain_values.items():
        set_config_value(db, key, value, description=NOTIFICATION_CONFIG_DESCRIPTIONS.get(key))

    for key, value in secret_values.items():
        if value is None:
            continue
        set_config_value(
            db,
            key,
            value.strip(),
            encrypted=True,
            description=NOTIFICATION_CONFIG_DESCRIPTIONS.get(key),
        )

    return get_notification_config_payload(db)


@router.put("/vpn", response_model=VPNConfigResponse)
def update_vpn_config(config: VPNConfigUpdate, db: Session = Depends(get_db)):
    """Update VPN configuration."""
    if config.account_number is not None:
        set_config_value(
            db, 
            "vpn_account_number", 
            config.account_number, 
            encrypted=True,
            description="Mullvad VPN account number"
        )

    if config.socks_proxy is not None:
        set_config_value(
            db,
            "mullvad_socks_proxy",
            config.socks_proxy,
            encrypted=True,
            description="SOCKS5 proxy URL for crawler VPN routing"
        )
    
    set_config_value(
        db, 
        "vpn_enabled", 
        "true" if config.enabled else "false",
        description="Whether VPN is enabled for crawling"
    )
    
    set_config_value(
        db, 
        "vpn_auto_rotate", 
        "true" if config.auto_rotate else "false",
        description="Automatically rotate VPN servers"
    )
    
    set_config_value(
        db, 
        "vpn_rotate_interval_minutes", 
        str(config.rotate_interval_minutes),
        description="Minutes between VPN server rotations"
    )
    
    return get_vpn_config(db)


@router.post("/vpn/test", response_model=VPNStatusResponse)
async def test_vpn_connection(db: Session = Depends(get_db)):
    """Test VPN connection with current configuration."""
    result = {
        "connected": False,
        "ip": None,
        "country": None,
        "mullvad_exit_ip": False,
        "error": None,
    }

    async def fetch_json(client: httpx.AsyncClient, url: str):
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

    async def fetch_text(client: httpx.AsyncClient, url: str):
        response = await client.get(url)
        response.raise_for_status()
        return response.text.strip()

    proxy_url = get_effective_proxy_url(db)
    gluetun_enabled = proxy_targets_gluetun(proxy_url)

    try:
        if gluetun_enabled:
            control_base_url = get_gluetun_control_base_url()
            try:
                async with httpx.AsyncClient(timeout=5) as control_client:
                    try:
                        payload = await fetch_json(control_client, f"{control_base_url}/v1/publicip/ip")
                        public_ip = payload.get("public_ip") or payload.get("ip")
                    except Exception:
                        public_ip = await fetch_text(control_client, f"{control_base_url}/ip")

                    if public_ip:
                        result["connected"] = True
                        result["ip"] = public_ip
            except Exception as control_exc:
                result["error"] = f"Gluetun control server check failed: {control_exc}"

        client_kwargs = {"timeout": 10}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        elif gluetun_enabled:
            client_kwargs["timeout"] = 10

        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                payload = await fetch_json(client, "https://am.i.mullvad.net/json")
                result["connected"] = True
                result["ip"] = payload.get("ip")
                result["country"] = payload.get("country") or payload.get("country_code")
                result["mullvad_exit_ip"] = bool(payload.get("mullvad_exit_ip", False))
                return VPNStatusResponse(**result)
            except Exception as mullvad_exc:
                payload = await fetch_json(client, "https://ipinfo.io/json")
                result["connected"] = True
                result["ip"] = payload.get("ip")
                result["country"] = payload.get("country")
                result["mullvad_exit_ip"] = False
                existing_error = result["error"]
                fallback_message = f"Mullvad check failed, fallback succeeded: {mullvad_exc}"
                result["error"] = f"{existing_error}; {fallback_message}" if existing_error else fallback_message
                return VPNStatusResponse(**result)
    except Exception as exc:
        if result["connected"]:
            existing_error = result["error"]
            final_message = f"Proxy validation failed after Gluetun tunnel check: {exc}"
            result["error"] = f"{existing_error}; {final_message}" if existing_error else final_message
            return VPNStatusResponse(**result)
        result["error"] = str(exc)
        return VPNStatusResponse(**result)


@router.get("/all", response_model=List[ConfigResponse])
def get_all_config(db: Session = Depends(get_db)):
    """Get all configuration values (values are masked for encrypted entries)."""
    configs = db.query(Config).all()
    
    # Mask encrypted values
    result = []
    for config in configs:
        config_dict = {
            "id": config.id,
            "key": config.key,
            "value": "********" if config.encrypted else config.value,
            "encrypted": config.encrypted,
            "description": config.description,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        }
        result.append(ConfigResponse(**config_dict))
    
    return result
