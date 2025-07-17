from pydantic import BaseModel, Field
from typing import Optional

class PermissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)

class PermissionOut(PermissionBase):
    id: int

    class Config:
        orm_mode = True
