from pydantic import BaseModel
from typing import Optional


class ChatHistoryBase(BaseModel):
    session_id: str
    message: str
    response: str
    model_used: Optional[str]
    tokens_used: Optional[int]

class ChatHistoryCreate(ChatHistoryBase):
    pass

class ChatHistoryOut(ChatHistoryBase):
    id: int
    user_id: int
    created_at: Optional[str]

    class Config:
        orm_mode = True
