from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StrategyBase(BaseModel):
    name: str
    description: Optional[str] = None
    steps: list[str] = []

class StrategyCreate(StrategyBase):
    pass

class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[list[str]] = None

class StrategyOut(StrategyBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True  # Pydantic v2: reemplaza orm_mode
