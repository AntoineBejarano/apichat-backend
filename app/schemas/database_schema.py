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
    # 🔧 CORREGIDO: Todos los campos son opcionales para permitir actualizaciones parciales
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    # 🔧 NUEVO: Campo para actualizar estado del schema
    schema_status: Optional[str] = None

    model_config = {
        "from_attributes": False
    }

class DatabaseConnectionOut(DatabaseConnectionBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    # 🔧 NUEVO: Campo para mostrar estado del schema
    schema_status: Optional[str]

    model_config = {
        "from_attributes": True
    }

class DatabaseConnectionCreateResponse(BaseModel):
    """
    Respuesta del endpoint de creación de conexión.
    Incluye la conexión creada y información sobre el proceso de generación de schema.
    """
    connection: DatabaseConnectionOut
    message: str
    schema_status: str
    estimated_time: str

    model_config = {
        "from_attributes": False
    }
