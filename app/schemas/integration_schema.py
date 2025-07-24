from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class IntegrationBase(BaseModel):
    name: str
    provider: str
    metadata: Optional[dict] = {}

    model_config = {
        "from_attributes": False
    }

class IntegrationCreate(IntegrationBase):
    pass

class IntegrationOut(IntegrationBase):
    id: UUID
    user_id: UUID
    access_token: Optional[str]
    refresh_token: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {
        "from_attributes": True
    }
