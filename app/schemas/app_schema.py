from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.schemas.mcp_integration_schema import MCPIntegrationInDB


class AppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AppCreate(AppBase):
    is_public: Optional[bool] = False
    mcp_integration_id: Optional[int] = None  # 👈 Nuevo campo


class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    mcp_integration_id: Optional[int] = None  # 👈 Nuevo campo


class AppOut(AppBase):
    id: int
    user_id: int
    is_public: bool
    mcp_integration_id: Optional[int] = None
    mcp_integration: Optional[MCPIntegrationInDB] = None  # 👈 Para retornar el objeto si lo necesitas
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
