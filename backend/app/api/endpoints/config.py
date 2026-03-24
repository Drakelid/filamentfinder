from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
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
)

router = APIRouter(dependencies=[Depends(require_admin_api_key)])


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


@router.get("/vpn", response_model=VPNConfigResponse)
def get_vpn_config(db: Session = Depends(get_db)):
    """Get VPN configuration."""
    account_number = get_config_value(db, "vpn_account_number", "")
    enabled = get_config_value(db, "vpn_enabled", "false") == "true"
    auto_rotate = get_config_value(db, "vpn_auto_rotate", "true") == "true"
    rotate_interval = int(get_config_value(db, "vpn_rotate_interval_minutes", "30"))
    
    # Check if Mullvad account is configured (worker runs through Gluetun VPN container)
    mullvad_account = os.environ.get("MULLVAD_ACCOUNT_NUMBER", "")
    
    # VPN is connected if account number is configured (worker uses network_mode: service:mullvad)
    connected = bool(mullvad_account)
    current_server = "Gluetun/Mullvad (Nordic: NO/SE/DK/FI)" if connected else None
    current_ip = None
    
    return VPNConfigResponse(
        account_number_set=bool(account_number),
        enabled=enabled,
        auto_rotate=auto_rotate,
        rotate_interval_minutes=rotate_interval,
        connected=connected,
        current_server=current_server,
        current_ip=current_ip,
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
def test_vpn_connection(db: Session = Depends(get_db)):
    """Test VPN connection with current configuration."""
    account_number = get_config_value(db, "vpn_account_number", "")
    
    if not account_number:
        raise HTTPException(status_code=400, detail="VPN account number not configured")
    
    # TODO: Actually test VPN connection
    # For now, return a placeholder response
    return VPNStatusResponse(
        connected=False,
        current_server=None,
        current_ip=None,
        account_valid=bool(account_number),
    )


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
