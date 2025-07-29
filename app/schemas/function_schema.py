from pydantic import BaseModel, Field, model_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class FunctionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    code: Optional[str] = None  # ✅ Ahora opcional
    timeout: Optional[int] = 30
    is_enabled: Optional[bool] = True

    model_config = {
        "from_attributes": False
    }


class FunctionCreate(FunctionBase):
    app_id: UUID
    integration_id: Optional[UUID] = None

    @model_validator(mode='after')
    def validate_code_requirement(self):
        if self.integration_id is None and not self.code:
            raise ValueError("El campo 'code' es obligatorio para funciones internas (sin integración)")
        return self


class FunctionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    code: Optional[str] = None
    timeout: Optional[int] = None
    is_enabled: Optional[bool] = None
    integration_id: Optional[UUID] = None

    model_config = {
        "from_attributes": False
    }


class FunctionOut(FunctionBase):
    id: UUID
    app_id: UUID
    integration_id: Optional[UUID] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "a12e4567-e89b-12d3-a456-426614174000",
                "app_id": "b98e4567-e89b-12d3-a456-426614174111",
                "name": "Mi función",
                "description": "Hace algo increíble",
                "code": "def handler(): return 'Hola mundo'",
                "timeout": 30,
                "is_enabled": True,
                "integration_id": "c11e4567-e89b-12d3-a456-426614174222",
                "created_at": "2025-07-29T15:00:00Z",
                "updated_at": "2025-07-29T15:30:00Z"
            }
        }
    }
