from uuid import UUID
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime

class EventTriggerBase(BaseModel):
    event_definition_id: UUID
    config: Dict = Field(..., json_schema_extra={"example": {
        "connection_id": "xxx",
        "table_name": "leads",
        "time_field": "created_at"
    }})

class EventTriggerCreate(EventTriggerBase):
    pass

class EventTriggerOut(EventTriggerBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
