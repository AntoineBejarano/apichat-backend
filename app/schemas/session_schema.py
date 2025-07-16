from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SessionCreate(BaseModel):
    user_id: int
    user_agent: Optional[str]
    ip_address: Optional[str]

class SessionOut(SessionCreate):
    id: int
    session_token: str
    created_at: datetime

    class Config:
        orm_mode = True
