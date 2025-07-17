# app/schemas/chat_schema.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ChatBase(BaseModel):
    system_prompt: Optional[str] = None
    title: Optional[str] = None
    app_id: Optional[int] = None
    agent_id: Optional[int] = None
    database_id: Optional[int] = None


class ChatCreate(ChatBase):
    pass


class ChatOut(ChatBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system", "function"
    content: str
    name: Optional[str] = None
    timestamp: Optional[datetime] = None
