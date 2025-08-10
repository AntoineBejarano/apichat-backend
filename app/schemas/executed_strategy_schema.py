from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class ExecutedStrategyBase(BaseModel):
    user_id: UUID
    chat_id: UUID
    plan_json: Any = Field(..., description="Plan en formato JSON generado por la IA")
    result_summary: Optional[str] = None
    is_public: bool = False
    source: str = "ai_generated"


class ExecutedStrategyCreate(ExecutedStrategyBase):
    pass


class ExecutedStrategyUpdate(BaseModel):
    result_summary: Optional[str] = None
    is_public: Optional[bool] = None


class ExecutedStrategyOut(ExecutedStrategyBase):
    id: UUID
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
