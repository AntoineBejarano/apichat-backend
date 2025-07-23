from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class FunctionBase(BaseModel):
    name: str
    description: Optional[str]
    parameters: Optional[Dict]
    execution_type: str
    method: Optional[str]
    url: Optional[str]
    headers: Optional[Dict]
    body: Optional[Dict]
    code: Optional[str]
    active: Optional[bool] = True

    model_config = {
        "from_attributes": False
    }

class FunctionCreate(FunctionBase):
    app_id: Optional[int]
    integration_id: Optional[int]

class FunctionUpdate(BaseModel):
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

    model_config = {
        "from_attributes": False
    }

class FunctionOut(FunctionBase):
    id: int
    app_id: Optional[int]
    integration_id: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
