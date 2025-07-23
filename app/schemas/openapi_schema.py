from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OpenAPIIntegrationCreate(BaseModel):
    title: str
    version: Optional[str]
    base_url: Optional[str]
    raw_json: str

    model_config = {
        "from_attributes": False
    }

class OpenAPIIntegrationOut(BaseModel):
    id: int
    title: str
    version: Optional[str]
    base_url: Optional[str]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
