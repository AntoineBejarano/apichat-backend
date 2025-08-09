from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class EventDefinitionBase(BaseModel):
    name: str = Field(..., example="new_row_in_table")
    group: str = Field(..., example="database")  # Ej: 'database', 'webhook', 'api'
    description: Optional[str] = Field(None, example="Dispara al insertar una nueva fila")
    required_fields: List[str] = Field(..., example=["connection_id", "table_name", "time_field"])

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

    class Config:
        from_attributes = True
