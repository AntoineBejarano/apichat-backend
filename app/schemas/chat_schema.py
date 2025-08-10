from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# Base model for Chat objects
class ChatBase(BaseModel):
    system_prompt: Optional[str] = None
    title: Optional[str] = None
    app_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    database_id: Optional[UUID] = None

    @field_validator("app_id", "agent_id", "database_id", mode="before")
    @classmethod
    def convert_zero_to_none(cls, value):
        """Converts invalid values (0, '0', '') to None."""
        if value in (0, "0", "", None):
            return None
        return value

    model_config = {
        "from_attributes": False
    }


# For creating a new chat
class ChatCreate(ChatBase):
    pass


# For returning chat data to the client
class ChatOut(ChatBase):
    chat_id: UUID = Field(..., alias="id")
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        "populate_by_name": True  # Ensures alias `chat_id` is used instead of `id`
    }


# Individual message in the chat (used in WebSocket)
class ChatMessage(BaseModel):
    role: str  # e.g., "user", "assistant", "system"
    content: str
    name: Optional[str] = None
    timestamp: Optional[datetime] = None
    explorer: Optional[bool] = False
    # 🔧 FIX: Usar default_factory para evitar defaults mutables compartidos
    db_ids: Optional[List[UUID]] = Field(default_factory=list)
    app_ids: Optional[List[UUID]] = Field(default_factory=list)

    def model_dump(self, **kwargs):
        """Override model_dump to handle timestamp automatically"""
        data = super().model_dump(**kwargs)
        # Si timestamp es None, no lo incluimos en el JSON
        if data.get("timestamp") is None:
            data.pop("timestamp", None)
        return data

    model_config = {
        "from_attributes": False
    }
