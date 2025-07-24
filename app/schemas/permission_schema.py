from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

class PermissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)

    model_config = {
        "from_attributes": False
    }

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)

    model_config = {
        "from_attributes": False
    }

class PermissionOut(PermissionBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }
