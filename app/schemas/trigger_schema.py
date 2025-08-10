from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

class TriggerBase(BaseModel):
    event_trigger_id: UUID
    strategy_id: Optional[UUID]
    app_id: Optional[str] = Field(None, example="instantly")
    function_name: Optional[str] = Field(None, example="send_email")
    filter_condition: Optional[Dict] = Field(None, example={"country": "ES"})
    interval_seconds: Optional[int] = Field(60, ge=1)
    enabled: Optional[bool] = True

class TriggerCreate(TriggerBase):
    pass

class TriggerOut(TriggerBase):
    id: UUID
    user_id: UUID
    last_checked: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
