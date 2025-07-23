from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatBase(BaseModel):
    system_prompt: Optional[str] = None
    title: Optional[str] = None
    app_id: Optional[int] = None
    agent_id: Optional[int] = None
    database_id: Optional[int] = None

    model_config = {
        "from_attributes": False
    }

class ChatCreate(ChatBase):
    pass

class ChatOut(ChatBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    timestamp: Optional[datetime] = None

    model_config = {
        "from_attributes": False
    }
