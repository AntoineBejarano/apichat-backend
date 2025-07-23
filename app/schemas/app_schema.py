from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.schemas.mcp_integration_schema import MCPIntegrationInDB
from app.schemas.proxy_schema import ProxyOut  # 👈 Si quieres retornar también el proxy completo

class AppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    model_config = {
        "from_attributes": False,
    }

class AppCreate(AppBase):
    is_public: Optional[bool] = False
    mcp_integration_id: Optional[int] = None
    proxy_id: Optional[int] = None  # 👈 Nuevo campo opcional

    # Hereda model_config de AppBase

class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    mcp_integration_id: Optional[int] = None
    proxy_id: Optional[int] = None  # 👈 Nuevo campo opcional

    model_config = {
        "from_attributes": False,
    }

class AppOut(AppBase):
    id: int
    user_id: int
    is_public: bool
    mcp_integration_id: Optional[int] = None
    mcp_integration: Optional[MCPIntegrationInDB] = None
    proxy_id: Optional[int] = None  # 👈 Devuelve solo el ID
    # proxy: Optional[ProxyOut] = None  # 👈 (Descomenta si quieres retornar el objeto Proxy)
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        # Si quieres, puedes añadir ejemplos al esquema JSON:
        "json_schema_extra": {
            "example": {
                "id": 1,
                "user_id": 42,
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
