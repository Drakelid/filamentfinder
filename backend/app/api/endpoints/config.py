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

    return WIREGUARD_ENDPOINT_PATTERN.sub(replace_endpoint, config_text)


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


@router.get("/vpn", response_model=VPNConfigResponse)
def get_vpn_config(db: Session = Depends(get_db)):
    """Get VPN configuration."""
    account_number = get_config_value(db, "vpn_account_number", "")
    proxy_url = get_config_value(db, "mullvad_socks_proxy", "") or os.environ.get("MULLVAD_SOCKS_PROXY", "")
    gluetun_enabled = os.environ.get("GLUETUN_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    enabled = get_config_value(db, "vpn_enabled", "false") == "true"
    auto_rotate = get_config_value(db, "vpn_auto_rotate", "true") == "true"
    rotate_interval = int(get_config_value(db, "vpn_rotate_interval_minutes", "30"))
    wireguard_file_configured, wireguard_file_name, wireguard_uploaded_at, wireguard_profile_count, wireguard_active_file_name = get_wireguard_file_metadata(db)

    connected = enabled and (bool(proxy_url) or gluetun_enabled)
    proxy_host = get_proxy_host(proxy_url)
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

    proxy_url = get_config_value(db, "mullvad_socks_proxy", "") or os.environ.get("MULLVAD_SOCKS_PROXY", "")
    gluetun_enabled = os.environ.get("GLUETUN_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}

    try:
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
                result["error"] = f"Mullvad check failed, fallback succeeded: {mullvad_exc}"
                return VPNStatusResponse(**result)
    except Exception as exc:
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
