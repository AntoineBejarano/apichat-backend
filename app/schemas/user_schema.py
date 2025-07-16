from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str]

class UserCreate(UserBase):
    password: str  # si usas login propio además de OAuth

class UserOut(UserBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    is_admin: Optional[bool] = False

    class Config:
        orm_mode = True
        
class UserUpdate(BaseModel):
    name: Optional[str]
    password: Optional[str]  # Permite cambiar contraseña

    class Config:
        orm_mode = True


# Opcional: usuario detallado con sus relaciones (apps, agentes, etc.)
class UserDetail(UserOut):
    apps: List["AppOut"] = []
    agents: List["AgentOut"] = []
    strategies: List["StrategyOut"] = []
    functions: List["FunctionOut"] = []
    integrations: List["IntegrationOut"] = []

# Evita errores de referencia circular
from app.schemas.app_schema import AppOut
from app.schemas.agent_schema import AgentOut
from app.schemas.strategy_schema import StrategyOut
from app.schemas.function_schema import FunctionOut
from app.schemas.integration_schema import IntegrationOut
