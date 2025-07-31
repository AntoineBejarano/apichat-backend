from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class ChatHistoryBase(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    token_count: Optional[int] = None
    is_function_call: bool = False
    function_call_id: Optional[int] = None

    model_config = {
        "from_attributes": False
    }

class ChatHistoryCreate(ChatHistoryBase):
    chat_id: UUID  # Cambiado a UUID

class ChatHistoryOut(ChatHistoryBase):
    id: UUID
    chat_id: UUID  # Cambiado a UUID
    timestamp: datetime

    model_config = {
        "from_attributes": True
    }
