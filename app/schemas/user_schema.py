from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

from app.schemas.app_schema import AppOut
from app.schemas.agent_schema import AgentOut
from app.schemas.strategy_schema import StrategyOut
from app.schemas.function_schema import FunctionOut
from app.schemas.integration_schema import IntegrationOut

# 🎯 FASE 12: Esquemas para preferencias de usuario
class UserPreferences(BaseModel):
    """Preferencias de usuario para personalizar la experiencia."""
    response_format: Literal["detailed", "concise", "minimal"] = Field(
        default="detailed", 
        description="Formato de respuesta preferido"
    )
    detail_level: Literal["low", "medium", "high"] = Field(
        default="medium", 
        description="Nivel de detalle preferido"
    )
    risk_tolerance: Literal["low", "medium", "high"] = Field(
        default="medium", 
        description="Tolerancia al riesgo del usuario"
    )
    confirmations: bool = Field(
        default=True, 
        description="Si requiere confirmaciones para acciones de riesgo"
    )
    language: Literal["es", "en", "fr", "de"] = Field(
        default="es", 
        description="Idioma preferido del usuario"
    )
    timezone: str = Field(
        default="UTC", 
        description="Zona horaria del usuario"
    )

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

    model_config = {"from_attributes": False}

class UserCreate(UserBase):
    password: Optional[str] = None
    preferences: Optional[UserPreferences] = None

class UserOut(UserBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_admin: Optional[bool] = False
    # 🎯 FASE 12: Incluir preferencias en la salida
    preferences: UserPreferences

    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    # 🎯 FASE 12: Permitir actualización de preferencias
    preferences: Optional[UserPreferences] = None

    model_config = {"from_attributes": False}

class UserDetail(UserOut):
    apps: List[AppOut] = []
    agents: List[AgentOut] = []
    strategies: List[StrategyOut] = []
    functions: List[FunctionOut] = []
    integrations: List[IntegrationOut] = []

    model_config = {"from_attributes": True}

# 🎯 FASE 12: Esquemas específicos para preferencias
class UserPreferencesUpdate(BaseModel):
    """Esquema para actualizar solo las preferencias."""
    response_format: Optional[Literal["detailed", "concise", "minimal"]] = None
    detail_level: Optional[Literal["low", "medium", "high"]] = None
    risk_tolerance: Optional[Literal["low", "medium", "high"]] = None
    confirmations: Optional[bool] = None
    language: Optional[Literal["es", "en", "fr", "de"]] = None
    timezone: Optional[str] = None

class UserPreferencesResponse(BaseModel):
    """Respuesta con las preferencias actuales del usuario."""
    user_id: UUID
    preferences: UserPreferences
    updated_at: datetime
