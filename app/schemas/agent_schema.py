from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: Optional[str] = None
    user_id: Optional[int]
    is_shared: Optional[bool] = False

    model_config = {
        "from_attributes": False,  # normalmente False en tus esquemas base
    }

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    is_shared: Optional[bool] = None

    model_config = {
        "from_attributes": False,
    }

class AgentOut(AgentBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 123,
                "name": "Agente X",
                "description": "Descripción del agente",
                "prompt": "¿Cómo te ayudo hoy?",
                "user_id": 42,
                "is_shared": False,
                "created_at": "2025-07-23T12:34:56Z",
                "updated_at": "2025-07-23T12:34:56Z",
            }
        }
    }
