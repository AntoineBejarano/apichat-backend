from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

class ProxyBase(BaseModel):
    name: str = Field(..., max_length=100)
    base_url: str
    default_headers: Optional[Dict[str, str]] = None
    auth: Optional[Dict[str, str]] = None
    active: Optional[bool] = True

    model_config = {"from_attributes": False}

class ProxyCreate(ProxyBase):
    pass

class ProxyUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    default_headers: Optional[Dict[str, str]] = None
    auth: Optional[Dict[str, str]] = None
    active: Optional[bool] = None

    model_config = {"from_attributes": False}

class ProxyOut(ProxyBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}
