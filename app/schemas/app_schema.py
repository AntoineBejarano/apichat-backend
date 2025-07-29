from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.schemas.mcp_integration_schema import MCPIntegrationInDB
from app.schemas.proxy_schema import ProxyOut

class AppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    model_config = {
        "from_attributes": False,
    }

class AppCreate(AppBase):
    is_public: Optional[bool] = False
    mcp_integration_id: Optional[int] = None
    proxy_id: Optional[int] = None

class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    mcp_integration_id: Optional[int] = None
    proxy_id: Optional[int] = None

    model_config = {
        "from_attributes": False,
    }

class AppOut(AppBase):
    id: UUID
    user_id: UUID
    is_public: bool
    mcp_integration_id: Optional[int] = None
    mcp_integration: Optional[MCPIntegrationInDB] = None
    proxy_id: Optional[int] = None
    # proxy: Optional[ProxyOut] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "7dd28845-da05-4281-81c8-9bf12b66508d",
                "user_id": "f967cefb-56a7-48e5-bfbe-e3d8978964f4",
                "name": "Mi App",
                "description": "Descripción opcional",
                "is_public": False,
                "mcp_integration_id": None,
                "proxy_id": None,
                "created_at": "2025-07-23T10:00:00Z",
                "updated_at": "2025-07-23T10:00:00Z"
            }
        }
    }
