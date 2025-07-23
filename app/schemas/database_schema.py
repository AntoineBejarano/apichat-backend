from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class DatabaseConnectionBase(BaseModel):
    name: str
    db_type: str
    config: Dict

    model_config = {
        "from_attributes": False
    }

class DatabaseConnectionCreate(DatabaseConnectionBase):
    pass

class DatabaseConnectionUpdate(BaseModel):
    name: Optional[str]
    db_type: Optional[str]
    config: Optional[Dict]

    model_config = {
        "from_attributes": False
    }

class DatabaseConnectionOut(DatabaseConnectionBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
