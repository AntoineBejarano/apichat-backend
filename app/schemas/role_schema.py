from pydantic import BaseModel, Field
from typing import Optional, List

class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)

    model_config = {"from_attributes": False}

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)

    model_config = {"from_attributes": False}

class RoleOut(RoleBase):
    id: int
    permissions: List[str] = []

    model_config = {"from_attributes": True}
