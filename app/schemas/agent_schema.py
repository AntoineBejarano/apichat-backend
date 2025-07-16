from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: Optional[str] = None
    user_id: Optional[int]
    is_shared: Optional[bool] = False

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    is_shared: Optional[bool] = None

class AgentOut(AgentBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
