from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class DatabaseConnectionBase(BaseModel):
    name: str
    db_type: str
    host: str
    port: int
    database: str
    username: str
    password: str

    model_config = {
        "from_attributes": False
    }

class DatabaseConnectionCreate(DatabaseConnectionBase):
    pass

class DatabaseConnectionUpdate(BaseModel):
    name: Optional[str]
    db_type: Optional[str]
    host: Optional[str]
    port: Optional[int]
    database: Optional[str]
    username: Optional[str]
    password: Optional[str]

    model_config = {
        "from_attributes": False
    }

class DatabaseConnectionOut(DatabaseConnectionBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
