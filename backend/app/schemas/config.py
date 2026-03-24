from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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
    enabled: bool = False
    auto_rotate: bool = True
    rotate_interval_minutes: int = 30


class VPNConfigResponse(BaseModel):
    """Schema for VPN configuration response."""
    account_number_set: bool
    enabled: bool
    auto_rotate: bool
    rotate_interval_minutes: int
    connected: bool
    current_server: Optional[str] = None
    current_ip: Optional[str] = None


class VPNStatusResponse(BaseModel):
    """Schema for VPN status response."""
    connected: bool
    current_server: Optional[str] = None
    current_ip: Optional[str] = None
    account_valid: bool
