# schemas/strategy_schema.py

from pydantic import BaseModel
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime
import enum

class TriggerTypeEnum(str, enum.Enum):
    EVENT = "event"
    CRON = "cron"
    MANUAL = "manual"


class StepSchema(BaseModel):
    function_id: UUID
    inputs: Dict[str, str]


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: TriggerTypeEnum
    trigger_config: Optional[Dict[str, str]] = None
    steps: List[StepSchema]


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[TriggerTypeEnum] = None
    trigger_config: Optional[Dict[str, str]] = None
    steps: Optional[List[StepSchema]] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None
    last_run_at: Optional[datetime] = None


class StrategyOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    trigger_type: TriggerTypeEnum
    trigger_config: Optional[Dict[str, str]]
    steps: List[StepSchema]
    is_active: bool
    last_run_at: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class TriggerSchema(BaseModel):
    type: TriggerTypeEnum
    config: Optional[Dict[str, str]] = None


class StrategyImportSchema(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: TriggerSchema
    steps: List[StepSchema]
