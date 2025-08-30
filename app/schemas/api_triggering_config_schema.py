from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class APITriggeringConfigBase(BaseModel):
    enabled: bool = True
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    max_auto_executions: int = Field(5, ge=1, le=20)
    timeout_seconds: int = Field(30, ge=5, le=300)
    allowed_endpoints: Optional[List[str]] = []
    blocked_endpoints: Optional[List[str]] = []
    auto_confirm: bool = False
    require_explicit_consent: bool = True


class APITriggeringConfigCreate(APITriggeringConfigBase):
    app_id: UUID


class APITriggeringConfigUpdate(APITriggeringConfigBase):
    pass


class APITriggeringConfigOut(APITriggeringConfigBase):
    id: UUID
    user_id: UUID
    app_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
