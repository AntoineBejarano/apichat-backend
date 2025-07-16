from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OpenAPIIntegrationCreate(BaseModel):
    title: str
    version: Optional[str]
    base_url: Optional[str]
    raw_json: str

class OpenAPIIntegrationOut(BaseModel):
    id: int
    title: str
    version: Optional[str]
    base_url: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
