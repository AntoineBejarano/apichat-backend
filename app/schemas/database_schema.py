from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class DatabaseConnectionBase(BaseModel):
    name: str
    db_type: str  # Ej: "postgresql", "mysql", etc.
    config: Dict  # Contendrá host, port, dbname, user, password...

class DatabaseConnectionCreate(DatabaseConnectionBase):
    pass

class DatabaseConnectionUpdate(BaseModel):
    name: Optional[str]
    db_type: Optional[str]
    config: Optional[Dict]

class DatabaseConnectionOut(DatabaseConnectionBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
