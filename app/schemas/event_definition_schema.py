from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class EventDefinitionBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "new_row_in_table"})
    group: str = Field(..., json_schema_extra={"example": "database"})  # Ej: 'database', 'webhook', 'api'
    description: Optional[str] = Field(None, json_schema_extra={"example": "Dispara al insertar una nueva fila"})
    required_fields: List[str] = Field(..., json_schema_extra={"example": ["connection_id", "table_name", "time_field"]})

class EventDefinitionCreate(EventDefinitionBase):
    pass

class EventDefinitionUpdate(BaseModel):
    description: Optional[str]
    required_fields: Optional[List[str]]
    is_active: Optional[bool]

class EventDefinitionOut(EventDefinitionBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
