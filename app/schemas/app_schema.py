from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class AppCreate(AppBase):
    is_public: Optional[bool] = False

class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None

class AppOut(AppBase):
    id: int
    user_id: int
    is_public: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
