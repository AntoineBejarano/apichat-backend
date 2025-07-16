from pydantic import BaseModel
from typing import Optional


class IntegrationBase(BaseModel):
    name: str
    provider: str
    metadata: Optional[dict] = {}

class IntegrationCreate(IntegrationBase):
    pass

class IntegrationOut(IntegrationBase):
    id: int
    user_id: int
    access_token: Optional[str]
    refresh_token: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        orm_mode = True
