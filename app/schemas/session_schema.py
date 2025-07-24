from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class SessionCreate(BaseModel):
    user_id: UUID  # también aquí si es UUID en tu modelo
    user_agent: Optional[str]
    ip_address: Optional[str]

    model_config = {"from_attributes": False}

class SessionOut(BaseModel):
    id: UUID
    user_id: UUID
    session_token: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime
    is_current: Optional[bool] = False

    model_config = {"from_attributes": True}
