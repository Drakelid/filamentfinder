"""Mullvad VPN integration for crawler anonymity.

The worker container runs through the Mullvad VPN using Gluetun (network_mode: service:mullvad).
All traffic from the worker is automatically routed through the VPN - no SOCKS5 proxy needed.

To configure Mullvad VPN:
1. Log in to your Mullvad account at https://mullvad.net/en/account/#/wireguard-config
2. Generate a WireGuard key or use an existing one
3. Set MULLVAD_WIREGUARD_PRIVATE_KEY and MULLVAD_WIREGUARD_ADDRESSES in .env
4. Restart the containers with: docker compose up -d

The VPN automatically connects to Nordic servers (Norway, Sweden, Denmark, Finland).
"""
import asyncio
import json
import random
import os
import shutil
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import urlparse

import docker
from cryptography.fernet import Fernet, InvalidToken
import structlog

from worker.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Mullvad server locations - Nordic countries only
PREFERRED_LOCATIONS = [
    "no",  # Norway
    "se",  # Sweden
    "dk",  # Denmark
    "fi",  # Finland
]

# Mullvad SOCKS5 proxy servers (Nordic)
# These are Mullvad's public SOCKS5 proxy endpoints
MULLVAD_SOCKS5_SERVERS = [
    # Format: (hostname, country)
    ("no-osl-socks5-001.mullvad.net", "no"),  # Oslo, Norway
    ("se-sto-socks5-001.mullvad.net", "se"),  # Stockholm, Sweden
    ("se-got-socks5-001.mullvad.net", "se"),  # Gothenburg, Sweden
    ("dk-cph-socks5-001.mullvad.net", "dk"),  # Copenhagen, Denmark
    ("fi-hel-socks5-001.mullvad.net", "fi"),  # Helsinki, Finland
]

SOCKS5_PORT = 1080
GLUETUN_WIREGUARD_DIR = Path("/gluetun/wireguard")
GLUETUN_WIREGUARD_FILE = GLUETUN_WIREGUARD_DIR / "wg0.conf"
GLUETUN_WIREGUARD_PROFILES_DIR = GLUETUN_WIREGUARD_DIR / "profiles"


@dataclass
class VPNStatus:
    """Current VPN connection status."""
    connected: bool
    server: Optional[str] = None
    ip: Optional[str] = None
    location: Optional[str] = None
    last_rotation: Optional[datetime] = None


def _load_wireguard_profiles_from_db() -> tuple[list[dict], Optional[str]]:
    from sqlalchemy import text
    from worker.database import get_db_session

    db = get_db_session()
    try:
        rows = db.execute(
            text(
                "SELECT key, value, encrypted FROM config "
                "WHERE key IN ('vpn_wireguard_profiles_json', 'vpn_wireguard_active_file_name')"
            )
        )
        config = {row[0]: _decrypt_if_needed(row[1], row[2]) for row in rows}
        try:
            profiles = json.loads(config.get("vpn_wireguard_profiles_json", "[]"))
        except json.JSONDecodeError:
            profiles = []
        if not isinstance(profiles, list):
            profiles = []
        profiles = [profile for profile in profiles if isinstance(profile, dict) and profile.get("file_name")]
        active_file_name = config.get("vpn_wireguard_active_file_name", "") or None
        return profiles, active_file_name
    finally:
        db.close()


def _set_active_wireguard_profile(file_name: str):
    from sqlalchemy import text
    from worker.database import get_db_session

    profile_path = GLUETUN_WIREGUARD_PROFILES_DIR / file_name
    if not profile_path.exists():
        raise FileNotFoundError(f"WireGuard profile {file_name} does not exist")

    GLUETUN_WIREGUARD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(profile_path, GLUETUN_WIREGUARD_FILE)

    db = get_db_session()
    try:
        existing = db.execute(
            text("SELECT id FROM config WHERE key = 'vpn_wireguard_active_file_name'")
        ).first()
        if existing:
            db.execute(
                text("UPDATE config SET value = :value, encrypted = false WHERE key = 'vpn_wireguard_active_file_name'"),
                {"value": file_name},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO config (key, value, encrypted, description) "
                    "VALUES ('vpn_wireguard_active_file_name', :value, false, 'Active WireGuard profile')"
                ),
                {"value": file_name},
            )
        db.commit()
    finally:
        db.close()


def _restart_gluetun_container():
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
        raise RuntimeError("Gluetun container was not found through the Docker socket")
    containers[0].restart(timeout=10)


def _get_gluetun_proxy_url() -> str:
    proxy_url = (settings.mullvad_socks_proxy or os.environ.get("MULLVAD_SOCKS_PROXY", "")).strip()
    if proxy_url:
        parsed = urlparse(proxy_url)
        if parsed.hostname == "gluetun":
            return proxy_url
    return "http://gluetun:8888"


class MullvadVPN:
    """Mullvad VPN controller supporting SOCKS5 proxy mode for Docker."""
    
    def __init__(self):
        self._status = VPNStatus(connected=False)
        self._account_number: Optional[str] = None
        self._enabled: bool = False
        self._auto_rotate: bool = True
        self._rotate_interval_minutes: int = 30
        self._last_rotation: Optional[datetime] = None
        self._rotation_task: Optional[asyncio.Task] = None
        self._current_proxy_index: int = 0
        self._gluetun_enabled = os.environ.get("GLUETUN_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        
        # Check for external SOCKS proxy configuration
        self._external_proxy = settings.mullvad_socks_proxy or os.environ.get("MULLVAD_SOCKS_PROXY", "")
    
    def configure(
        self,
        account_number: Optional[str] = None,
        enabled: bool = False,
        auto_rotate: bool = True,
        rotate_interval_minutes: int = 30,
    ):
        """Configure VPN settings."""
        if account_number:
            self._account_number = account_number
        self._enabled = enabled
        self._auto_rotate = auto_rotate
        self._rotate_interval_minutes = rotate_interval_minutes
        
        logger.info(
            "VPN configured",
            enabled=enabled,
            auto_rotate=auto_rotate,
            rotate_interval=rotate_interval_minutes,
            account_set=bool(self._account_number),
            mode="socks5_proxy",
        )
    
    async def set_account(self, account_number: str) -> bool:
        """Set the Mullvad account number (stored for SOCKS5 auth if needed)."""
        self._account_number = account_number
        logger.info("Mullvad account configured for SOCKS5 proxy authentication")
        return True
    
    async def connect(self) -> bool:
        """Enable the configured proxy path."""
        if not self._enabled:
            logger.debug("VPN not enabled, skipping connect")
            return False

        if self._gluetun_enabled:
            self._status.connected = True
            self._status.server = "Gluetun / Mullvad WireGuard"
            self._status.location = "Docker shared network"
            self._last_rotation = datetime.utcnow()
            logger.info("VPN connected via Gluetun network namespace")
            return True

        if self._external_proxy:
            profiles, active_file_name = _load_wireguard_profiles_from_db()
            self._status.connected = True
            self._status.server = active_file_name or urlparse(self._external_proxy).hostname or "SOCKS5 proxy"
            self._status.location = "Uploaded WireGuard profile" if profiles else "Proxy"
            self._last_rotation = datetime.utcnow()
            logger.info("VPN connected via configured proxy", server=self._status.server)
            return True

        self._status.connected = False
        self._status.server = None
        self._status.location = None
        logger.warning("VPN enabled but no SOCKS proxy configured")
        return False
    
    async def disconnect(self) -> bool:
        """Disable SOCKS5 proxy mode."""
        self._status = VPNStatus(connected=False)
        logger.info("VPN SOCKS5 proxy disabled")
        return True
    
    async def rotate_server(self) -> bool:
        """Rotate to a new SOCKS5 proxy server."""
        if not self._enabled:
            return False
        
        # Select a different server
        old_index = self._current_proxy_index
        available_indices = [i for i in range(len(MULLVAD_SOCKS5_SERVERS)) if i != old_index]
        self._current_proxy_index = random.choice(available_indices)
        
        server, location = MULLVAD_SOCKS5_SERVERS[self._current_proxy_index]
        
        self._status.server = server
        self._status.location = location
        self._last_rotation = datetime.utcnow()
        
        logger.info("VPN SOCKS5 proxy rotated", server=server, location=location)
        return True

    async def rotate_uploaded_wireguard_profile(self) -> bool:
        """Rotate to the next uploaded WireGuard profile and restart Gluetun."""
        profiles, active_file_name = _load_wireguard_profiles_from_db()
        if len(profiles) < 2:
            return False

        profile_names = [profile["file_name"] for profile in profiles]
        if active_file_name not in profile_names:
            next_file_name = profile_names[0]
        else:
            next_index = (profile_names.index(active_file_name) + 1) % len(profile_names)
            next_file_name = profile_names[next_index]

        _set_active_wireguard_profile(next_file_name)
        _restart_gluetun_container()

        self._status.server = next_file_name
        self._status.location = "Uploaded WireGuard profile"
        self._last_rotation = datetime.utcnow()
        logger.info("VPN WireGuard profile rotated", profile=next_file_name)
        return True
    
    async def get_status(self) -> VPNStatus:
        """Get current VPN status."""
        return self._status
    
    async def check_and_rotate(self) -> bool:
        """Check if rotation is needed and rotate if so."""
        if not self._enabled or not self._auto_rotate:
            return False
        
        if not self._last_rotation:
            return await self.rotate_server()
        
        elapsed = datetime.utcnow() - self._last_rotation
        if elapsed >= timedelta(minutes=self._rotate_interval_minutes):
            profiles, _ = _load_wireguard_profiles_from_db()
            if len(profiles) > 1:
                logger.info("VPN rotation interval reached, rotating uploaded WireGuard profile")
                return await self.rotate_uploaded_wireguard_profile()

            logger.info("VPN rotation interval reached, rotating SOCKS5 server")
            return await self.rotate_server()
        
        return False
    
    async def start_auto_rotation(self):
        """Start automatic server rotation task."""
        if self._rotation_task and not self._rotation_task.done():
            return
        
        async def rotation_loop():
            while self._enabled and self._auto_rotate:
                try:
                    await self.check_and_rotate()
                except Exception as e:
                    logger.error("VPN rotation error", error=str(e))
                
                # Check every minute
                await asyncio.sleep(60)
        
        self._rotation_task = asyncio.create_task(rotation_loop())
        logger.info("VPN auto-rotation started", interval_minutes=self._rotate_interval_minutes)
    
    async def stop_auto_rotation(self):
        """Stop automatic server rotation."""
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
            self._rotation_task = None
            logger.info("VPN auto-rotation stopped")
    
    def get_proxy_url(self) -> Optional[str]:
        """Get SOCKS5 proxy URL for HTTP client."""
        if not self._enabled or not self._status.connected:
            return None
        return self._external_proxy or None

    def get_playwright_proxy(self) -> Optional[dict]:
        proxy_url = self.get_proxy_url()
        if not proxy_url:
            return None

        parsed = urlparse(proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server = f"{server}:{parsed.port}"

        proxy = {"server": server}
        if parsed.username:
            proxy["username"] = parsed.username
        if parsed.password:
            proxy["password"] = parsed.password
        return proxy

    def require_proxy(self) -> str:
        if self._gluetun_enabled and self._enabled:
            return ""
        proxy_url = self.get_proxy_url()
        if proxy_url:
            return proxy_url
        if self._enabled:
            raise RuntimeError("VPN is enabled but no SOCKS5 proxy is configured")
        return ""
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    @property
    def is_connected(self) -> bool:
        return self._status.connected


# Global VPN instance
vpn_manager = MullvadVPN()


def _get_fernet() -> Fernet:
    return Fernet(os.environ["CONFIG_ENCRYPTION_KEY"].encode())


def _decrypt_if_needed(value: str, encrypted: bool) -> str:
    if not value:
        return ""
    if not encrypted:
        return value
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, KeyError):
        return ""


async def initialize_vpn_from_config():
    """Initialize VPN from database configuration."""
    from worker.database import get_db_session
    
    db = get_db_session()
    try:
        from sqlalchemy import text
        
        # Get VPN config from database
        result = db.execute(
            text("SELECT key, value, encrypted FROM config WHERE key LIKE 'vpn_%' OR key = 'mullvad_socks_proxy'")
        )
        config = {row[0]: _decrypt_if_needed(row[1], row[2]) for row in result}
        
        if not config:
            logger.info("No VPN configuration found in database")
            return
        
        account_number = config.get("vpn_account_number", "")
        uploaded_profiles, _ = _load_wireguard_profiles_from_db()
        if uploaded_profiles:
            socks_proxy = _get_gluetun_proxy_url()
        else:
            socks_proxy = config.get("mullvad_socks_proxy", "") or settings.mullvad_socks_proxy or os.environ.get("MULLVAD_SOCKS_PROXY", "")
        enabled = config.get("vpn_enabled", "false") == "true"
        auto_rotate = config.get("vpn_auto_rotate", "true") == "true"
        rotate_interval = int(config.get("vpn_rotate_interval_minutes", "30"))

        vpn_manager._external_proxy = socks_proxy
        
        vpn_manager.configure(
            account_number=account_number,
            enabled=enabled,
            auto_rotate=auto_rotate,
            rotate_interval_minutes=rotate_interval,
        )
        
        if enabled:
            if account_number:
                await vpn_manager.set_account(account_number)
            await vpn_manager.connect()
            if auto_rotate:
                await vpn_manager.start_auto_rotation()
                
    except Exception as e:
        logger.error("Failed to initialize VPN from config", error=str(e))
    finally:
        db.close()
