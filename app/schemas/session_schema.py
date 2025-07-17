from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SessionCreate(BaseModel):
    user_id: int
    user_agent: Optional[str]
    ip_address: Optional[str]


class SessionOut(BaseModel):
    id: int
    user_id: int
    session_token: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime
    is_current: Optional[bool] = False  # Se puede setear en el router comparando tokens

    class Config:
        orm_mode = True
