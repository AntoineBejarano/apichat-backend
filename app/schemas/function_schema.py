from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class FunctionBase(BaseModel):
    name: str
    description: Optional[str]
    parameters: Optional[Dict]
    execution_type: str  # "python" o "http"
    method: Optional[str]
    url: Optional[str]
    headers: Optional[Dict]
    body: Optional[Dict]
    code: Optional[str]
    active: Optional[bool] = True

class FunctionCreate(FunctionBase):
    app_id: Optional[int]
    integration_id: Optional[int]

class FunctionUpdate(FunctionBase):
    name: Optional[str]
    description: Optional[str]
    parameters: Optional[Dict]
    execution_type: Optional[str]
    method: Optional[str]
    url: Optional[str]
    headers: Optional[Dict]
    body: Optional[Dict]
    code: Optional[str]
    active: Optional[bool]

class FunctionOut(FunctionBase):
    id: int
    app_id: Optional[int]
    integration_id: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
