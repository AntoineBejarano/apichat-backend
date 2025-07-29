from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.schemas.app_schema import AppOut
from app.schemas.agent_schema import AgentOut
from app.schemas.strategy_schema import StrategyOut
from app.schemas.function_schema import FunctionOut
from app.schemas.integration_schema import IntegrationOut

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str]

    model_config = {"from_attributes": False}

class UserCreate(UserBase):
    password: Optional[str] = None

class UserOut(UserBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    is_admin: Optional[bool] = False

    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    name: Optional[str]
    password: Optional[str]

    model_config = {"from_attributes": False}

class UserDetail(UserOut):
    apps: List[AppOut] = []
    agents: List[AgentOut] = []
    strategies: List[StrategyOut] = []
    functions: List[FunctionOut] = []
    integrations: List[IntegrationOut] = []

    model_config = {"from_attributes": True}
