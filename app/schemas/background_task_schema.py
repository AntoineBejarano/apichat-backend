# app/schemas/background_task_schema.py
"""
Background Task Schemas
──────────────────────
Schemas para el manejo de tareas en background.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class TaskPriorityEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    """Schema para crear una nueva tarea en background"""
    task_type: str = Field(..., description="Tipo de tarea a ejecutar")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Datos de la tarea")
    priority: str = Field(default="normal", description="Prioridad de la tarea")


class TaskResponse(BaseModel):
    """Schema para respuesta de creación de tarea"""
    task_id: str = Field(..., description="ID único de la tarea")
    status: str = Field(..., description="Estado de la operación")
    message: str = Field(..., description="Mensaje descriptivo")


class TaskStatusResponse(BaseModel):
    """Schema para el estado de una tarea"""
    task_id: str = Field(..., description="ID único de la tarea")
    status: str = Field(..., description="Estado actual de la tarea")
    progress: float = Field(..., description="Progreso de la tarea (0-100)")
    created_at: datetime = Field(..., description="Fecha de creación")
    started_at: Optional[datetime] = Field(None, description="Fecha de inicio")
    completed_at: Optional[datetime] = Field(None, description="Fecha de finalización")
    result: Optional[Dict[str, Any]] = Field(None, description="Resultado de la tarea")
    error: Optional[str] = Field(None, description="Error si la tarea falló")
    retry_count: int = Field(..., description="Número de reintentos")


class TaskListResponse(BaseModel):
    """Schema para lista de tareas"""
    tasks: List[TaskStatusResponse] = Field(..., description="Lista de tareas")
    total_count: int = Field(..., description="Total de tareas")


class BackgroundServiceStats(BaseModel):
    """Schema para estadísticas del servicio de background"""
    active_tasks: int = Field(..., description="Número de tareas activas")
    completed_tasks: int = Field(..., description="Número de tareas completadas")
    queue_size: int = Field(..., description="Tamaño de la cola")
    workers: int = Field(..., description="Número de workers")
    is_running: bool = Field(..., description="Si el servicio está ejecutándose")


class TaskTypeInfo(BaseModel):
    """Schema para información de tipos de tareas"""
    task_type: str = Field(..., description="Tipo de tarea")
    description: str = Field(..., description="Descripción de la tarea")
    required_payload: List[str] = Field(..., description="Campos requeridos en payload")
    estimated_duration: str = Field(..., description="Duración estimada")
    priority_recommendation: str = Field(..., description="Prioridad recomendada")


# Información de tipos de tareas disponibles
TASK_TYPES_INFO = {
    "vector_search_update": TaskTypeInfo(
        task_type="vector_search_update",
        description="Actualizar embeddings de vector search para una base de datos",
        required_payload=["db_id"],
        estimated_duration="2-5 minutos",
        priority_recommendation="normal"
    ),
    "schema_cache_refresh": TaskTypeInfo(
        task_type="schema_cache_refresh",
        description="Refrescar cache de esquemas de base de datos",
        required_payload=["user_id", "db_id"],
        estimated_duration="30 segundos - 2 minutos",
        priority_recommendation="high"
    ),
    "performance_metrics_collection": TaskTypeInfo(
        task_type="performance_metrics_collection",
        description="Recolectar métricas de performance del sistema",
        required_payload=[],
        estimated_duration="10-30 segundos",
        priority_recommendation="low"
    ),
    "data_processing": TaskTypeInfo(
        task_type="data_processing",
        description="Procesar grandes volúmenes de datos",
        required_payload=["record_count"],
        estimated_duration="5-30 minutos",
        priority_recommendation="normal"
    ),
    "report_generation": TaskTypeInfo(
        task_type="report_generation",
        description="Generar reportes complejos",
        required_payload=["report_id"],
        estimated_duration="1-10 minutos",
        priority_recommendation="normal"
    )
}
