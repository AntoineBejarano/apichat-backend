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
    function_call_id: Optional[UUID] = None  # Ahora en UUID
    executed_strategy_id: Optional[UUID] = None  # 👈 Nuevo
    user_id: Optional[UUID] = None  # 👈 Para trazabilidad total

    model_config = {
        "from_attributes": False
    }


class ChatHistoryCreate(ChatHistoryBase):
    chat_id: UUID  # UUID obligatorio para creación


class ChatHistoryOut(ChatHistoryBase):
    id: UUID
    chat_id: UUID
    timestamp: datetime

    model_config = {
        "from_attributes": True
    }
