from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ChatHistoryBase(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    token_count: Optional[int] = None


class ChatHistoryCreate(ChatHistoryBase):
    chat_id: int


class ChatHistoryOut(ChatHistoryBase):
    id: int
    chat_id: int
    timestamp: datetime

    class Config:
        orm_mode = True
