from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_id: Optional[UUID] = None
    is_shared: Optional[bool] = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    language: Optional[str] = None
    memory_enabled: Optional[bool] = True

    model_config = {
        "from_attributes": False,
    }

class AgentCreate(AgentBase):
    app_ids: Optional[List[UUID]] = []
    database_connection_ids: Optional[List[UUID]] = []

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_shared: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    language: Optional[str] = None
    memory_enabled: Optional[bool] = None
    app_ids: Optional[List[UUID]] = None
    database_connection_ids: Optional[List[UUID]] = None

    model_config = {
        "from_attributes": False,
    }

class AgentOut(AgentBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    app_ids: Optional[List[UUID]] = []
    database_connection_ids: Optional[List[UUID]] = []

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "2cfdb3de-8c12-4dc4-b2cb-2d78dfba67d3",
                "name": "Agente X",
                "description": "Descripción del agente",
                "system_prompt": "¿Cómo te ayudo hoy?",
                "user_id": "f37b4cc2-b958-4f42-8493-8e9ee8db6b2c",
                "is_shared": False,
                "temperature": 0.7,
                "max_tokens": 512,
                "language": "es",
                "memory_enabled": True,
                "app_ids": ["a1a5e644-7d15-42cd-a85d-e18f2cfc3bc4"],
                "database_connection_ids": ["ae476dd5-9d3d-4cd4-bf9e-8e7c2316f72d"],
                "created_at": "2025-07-29T12:34:56Z",
                "updated_at": "2025-07-29T12:34:56Z"
            }
        }
    }
