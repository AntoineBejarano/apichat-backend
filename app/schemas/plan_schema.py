"""
Schemas de Pydantic para el sistema de Planes y To-dos.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class PlanStatus(str, Enum):
    """Estados de un plan."""
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class PlanPriority(str, Enum):
    """Prioridades de un plan."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Estados de una tarea."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionStatus(str, Enum):
    """Estados de ejecución."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


# ===== SCHEMAS DE TAREAS =====

class PlanTaskBase(BaseModel):
    """Schema base para tareas de plan."""
    title: str = Field(..., description="Título de la tarea")
    description: Optional[str] = Field(None, description="Descripción de la tarea")
    order_index: int = Field(..., description="Orden de ejecución")
    estimated_effort: Optional[int] = Field(5, description="Esfuerzo estimado en minutos")
    dependencies: List[str] = Field(default_factory=list, description="IDs de tareas dependientes")


class PlanTaskCreate(PlanTaskBase):
    """Schema para crear una tarea."""
    pass


class PlanTaskUpdate(BaseModel):
    """Schema para actualizar una tarea."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    estimated_effort: Optional[int] = None
    actual_effort: Optional[int] = None
    outcome: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


class PlanTaskOut(PlanTaskBase):
    """Schema de salida para tareas."""
    id: UUID
    plan_id: UUID
    status: TaskStatus
    actual_effort: Optional[int] = None
    outcome: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===== SCHEMAS DE PLANES =====

class UserPlanBase(BaseModel):
    """Schema base para planes de usuario."""
    title: str = Field(..., description="Título del plan")
    description: Optional[str] = Field(None, description="Descripción del plan")
    priority: PlanPriority = Field(PlanPriority.MEDIUM, description="Prioridad del plan")
    estimated_duration: Optional[int] = Field(None, description="Duración estimada en minutos")
    plan_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")


class UserPlanCreate(UserPlanBase):
    """Schema para crear un plan."""
    pass


class UserPlanUpdate(BaseModel):
    """Schema para actualizar un plan."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[PlanStatus] = None
    priority: Optional[PlanPriority] = None
    estimated_duration: Optional[int] = None
    actual_duration: Optional[int] = None
    plan_metadata: Optional[Dict[str, Any]] = None


class UserPlanOut(UserPlanBase):
    """Schema de salida para planes."""
    id: UUID
    user_id: UUID
    status: PlanStatus
    actual_duration: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tasks: List[PlanTaskOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ===== SCHEMAS DE ESTADO DE EJECUCIÓN =====

class PlanExecutionStateBase(BaseModel):
    """Schema base para estado de ejecución."""
    run_id: str = Field(..., description="ID único de la ejecución")
    redis_key: str = Field(..., description="Clave en Redis")
    current_task_index: int = Field(0, description="Índice de la tarea actual")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de ejecución")


class PlanExecutionStateCreate(PlanExecutionStateBase):
    """Schema para crear estado de ejecución."""
    pass


class PlanExecutionStateUpdate(BaseModel):
    """Schema para actualizar estado de ejecución."""
    current_task_index: Optional[int] = None
    status: Optional[ExecutionStatus] = None
    execution_metadata: Optional[Dict[str, Any]] = None


class PlanExecutionStateOut(PlanExecutionStateBase):
    """Schema de salida para estado de ejecución."""
    id: UUID
    plan_id: UUID
    status: ExecutionStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== SCHEMAS DE RESULTADOS =====

class PlanOutcomeBase(BaseModel):
    """Schema base para resultados de plan."""
    total_tasks: int = Field(..., description="Total de tareas")
    completed_tasks: int = Field(0, description="Tareas completadas")
    failed_tasks: int = Field(0, description="Tareas fallidas")
    skipped_tasks: int = Field(0, description="Tareas omitidas")
    total_estimated_time: Optional[int] = Field(None, description="Tiempo total estimado en minutos")
    total_actual_time: Optional[int] = Field(None, description="Tiempo total real en minutos")
    success_rate: int = Field(0, description="Porcentaje de éxito")
    outcome_summary: Optional[str] = Field(None, description="Resumen del resultado")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de ejecución")


class PlanOutcomeCreate(PlanOutcomeBase):
    """Schema para crear resultado de plan."""
    pass


class PlanOutcomeOut(PlanOutcomeBase):
    """Schema de salida para resultado de plan."""
    id: UUID
    plan_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ===== SCHEMAS DE GENERACIÓN =====

class PlanGenerationRequest(BaseModel):
    """Schema para solicitar generación de plan."""
    user_prompt: str = Field(..., description="Objetivo o consulta del usuario")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto adicional")
    database_info: Optional[Dict[str, Any]] = Field(None, description="Información de bases de datos")
    application_info: Optional[Dict[str, Any]] = Field(None, description="Información de aplicaciones")
    api_info: Optional[Dict[str, Any]] = Field(None, description="Información de APIs")


class PlanGenerationResponse(BaseModel):
    """Schema de respuesta para generación de plan."""
    plan: UserPlanOut
    tasks: List[PlanTaskOut]
    estimated_total_effort: int
    requires_confirmation: bool
    fallback_plan: Optional[str] = None


# ===== SCHEMAS DE EJECUCIÓN =====

class PlanExecutionRequest(BaseModel):
    """Schema para solicitar ejecución de plan."""
    plan_id: UUID = Field(..., description="ID del plan a ejecutar")
    auto_confirm: bool = Field(False, description="Si confirmar automáticamente")
    start_from_task: Optional[int] = Field(None, description="Índice de tarea desde la que empezar")


class PlanExecutionResponse(BaseModel):
    """Schema de respuesta para ejecución de plan."""
    execution_id: str
    plan_id: UUID
    status: ExecutionStatus
    current_task_index: int
    total_tasks: int
    message: str


class TaskExecutionUpdate(BaseModel):
    """Schema para actualizar ejecución de tarea."""
    task_id: UUID
    status: TaskStatus
    outcome: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    actual_effort: Optional[int] = None


# ===== SCHEMAS DE CONSULTA =====

class PlanQuery(BaseModel):
    """Schema para consultas de planes."""
    user_id: Optional[UUID] = None
    status: Optional[PlanStatus] = None
    priority: Optional[PlanPriority] = None
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class PlanListResponse(BaseModel):
    """Schema de respuesta para lista de planes."""
    plans: List[UserPlanOut]
    total: int
    limit: int
    offset: int