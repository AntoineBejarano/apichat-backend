from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class ChatBase(BaseModel):
    system_prompt: Optional[str] = None
    title: Optional[str] = None
    app_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    database_id: Optional[UUID] = None

    @field_validator("app_id", "agent_id", "database_id", mode="before")
    @classmethod
    def convert_zero_to_none(cls, value):
        if value in (0, "0", "", None):
            return None
        return value

    model_config = {
        "from_attributes": False
    }


class ChatCreate(ChatBase):
    pass


class ChatOut(ChatBase):
    chat_id: UUID = Field(..., alias="id")
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        "populate_by_name": True  # permite devolver chat_id en lugar de id
    }


class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    timestamp: Optional[datetime] = None

    model_config = {
        "from_attributes": False
    }
