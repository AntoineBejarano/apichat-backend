"""
🎯 FASE 13: Esquemas de telemetría y KPIs a nivel super pro.

Este archivo contiene todos los esquemas Pydantic para el sistema de telemetría
avanzado que mide el impacto UX y proporciona métricas detalladas de performance.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from enum import Enum


class TelemetryMode(str, Enum):
    """Modos de operación del sistema."""
    EXPLORER = "explorer"
    GUIDED = "guided"
    FAST_PATH = "fast_path"
    HYBRID = "hybrid"


class TelemetrySeverity(str, Enum):
    """Niveles de severidad para errores."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TelemetryPeriodType(str, Enum):
    """Tipos de períodos para agregación de métricas."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# 🎯 Esquemas base para métricas de conversación

class ConversationMetricsBase(BaseModel):
    """Esquema base para métricas de conversación."""
    chat_id: UUID
    user_id: UUID
    session_id: Optional[UUID] = None
    
    # Métricas de tokens y costos
    tokens_in: int = Field(..., ge=0, description="Tokens de entrada")
    tokens_out: int = Field(..., ge=0, description="Tokens de salida")
    estimated_cost_usd: Optional[Decimal] = Field(None, ge=0, description="Costo estimado en USD")
    
    # Métricas de performance
    latency_total_ms: Decimal = Field(..., ge=0, description="Latencia total en milisegundos")
    latency_llm_ms: Optional[Decimal] = Field(None, ge=0, description="Latencia del LLM")
    latency_db_ms: Optional[Decimal] = Field(None, ge=0, description="Latencia de base de datos")
    latency_cache_ms: Optional[Decimal] = Field(None, ge=0, description="Latencia de cache")
    
    # Métricas de cache
    cache_hit_ratio: Decimal = Field(..., ge=0, le=1, description="Ratio de aciertos de cache")
    cache_hits: int = Field(..., ge=0, description="Número de aciertos de cache")
    cache_misses: int = Field(..., ge=0, description="Número de fallos de cache")
    
    # Métricas de ejecución
    steps_executed: int = Field(..., ge=0, description="Pasos ejecutados")
    confirmations_required: int = Field(..., ge=0, description="Confirmaciones requeridas")
    errors_encountered: int = Field(..., ge=0, description="Errores encontrados")
    
    # Métricas de UX
    mode: TelemetryMode = Field(..., description="Modo de operación")
    intent_classification_confidence: Optional[Decimal] = Field(None, ge=0, le=1, description="Confianza de clasificación de intención")
    user_satisfaction_score: Optional[int] = Field(None, ge=1, le=5, description="Puntuación de satisfacción del usuario")
    
    # Métricas de recursos
    databases_accessed: int = Field(..., ge=0, description="Bases de datos accedidas")
    apps_accessed: int = Field(..., ge=0, description="Aplicaciones accedidas")
    functions_executed: int = Field(..., ge=0, description="Funciones ejecutadas")
    
    # Timestamps
    started_at: datetime = Field(..., description="Momento de inicio")
    completed_at: datetime = Field(..., description="Momento de finalización")
    
    # Metadata
    user_agent: Optional[str] = Field(None, description="User agent del cliente")
    ip_address: Optional[str] = Field(None, description="Dirección IP del cliente")
    country_code: Optional[str] = Field(None, max_length=2, description="Código de país")
    timezone: Optional[str] = Field(None, description="Zona horaria del usuario")
    
    # Preferencias del usuario
    user_response_format: Optional[str] = Field(None, description="Formato de respuesta preferido")
    user_detail_level: Optional[str] = Field(None, description="Nivel de detalle preferido")
    user_risk_tolerance: Optional[str] = Field(None, description="Tolerancia al riesgo del usuario")
    user_language: Optional[str] = Field(None, max_length=10, description="Idioma preferido del usuario")

    @validator('completed_at')
    def validate_completed_after_started(cls, v, values):
        """Valida que completed_at sea posterior a started_at."""
        if 'started_at' in values and v <= values['started_at']:
            raise ValueError('completed_at debe ser posterior a started_at')
        return v

    @validator('cache_hit_ratio')
    def validate_cache_hit_ratio(cls, v):
        """Valida que el ratio de cache esté entre 0 y 1."""
        if v < 0 or v > 1:
            raise ValueError('cache_hit_ratio debe estar entre 0 y 1')
        return v


class ConversationMetricsCreate(ConversationMetricsBase):
    """Esquema para crear métricas de conversación."""
    pass


class ConversationMetricsUpdate(BaseModel):
    """Esquema para actualizar métricas de conversación."""
    tokens_in: Optional[int] = Field(None, ge=0)
    tokens_out: Optional[int] = Field(None, ge=0)
    estimated_cost_usd: Optional[Decimal] = Field(None, ge=0)
    latency_total_ms: Optional[Decimal] = Field(None, ge=0)
    cache_hit_ratio: Optional[Decimal] = Field(None, ge=0, le=1)
    steps_executed: Optional[int] = Field(None, ge=0)
    errors_encountered: Optional[int] = Field(None, ge=0)
    user_satisfaction_score: Optional[int] = Field(None, ge=1, le=5)
    completed_at: Optional[datetime] = None


class ConversationMetricsResponse(ConversationMetricsBase):
    """Esquema de respuesta para métricas de conversación."""
    id: UUID
    total_tokens: int = Field(..., description="Total de tokens utilizados")
    duration_seconds: float = Field(..., description="Duración total en segundos")
    cost_per_token: Optional[Decimal] = Field(None, description="Costo promedio por token")
    success_rate: float = Field(..., description="Tasa de éxito de la conversación")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 🎯 Esquemas para métricas de pasos

class StepMetricsBase(BaseModel):
    """Esquema base para métricas de pasos."""
    step_number: int = Field(..., ge=1, description="Número del paso")
    step_type: str = Field(..., max_length=100, description="Tipo de paso")
    duration_ms: Decimal = Field(..., ge=0, description="Duración en milisegundos")
    success: bool = Field(True, description="Si el paso fue exitoso")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    tokens_used: int = Field(0, ge=0, description="Tokens utilizados en el paso")
    cache_operations: int = Field(0, ge=0, description="Operaciones de cache")
    database_queries: int = Field(0, ge=0, description="Consultas a base de datos")
    llm_calls: int = Field(0, ge=0, description="Llamadas al LLM")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata adicional del paso")
    started_at: datetime = Field(..., description="Momento de inicio del paso")
    completed_at: datetime = Field(..., description="Momento de finalización del paso")

    @validator('completed_at')
    def validate_completed_after_started(cls, v, values):
        """Valida que completed_at sea posterior a started_at."""
        if 'started_at' in values and v <= values['started_at']:
            raise ValueError('completed_at debe ser posterior a started_at')
        return v


class StepMetricsCreate(StepMetricsBase):
    """Esquema para crear métricas de pasos."""
    conversation_metrics_id: UUID = Field(..., description="ID de las métricas de conversación")


class StepMetricsResponse(StepMetricsBase):
    """Esquema de respuesta para métricas de pasos."""
    id: UUID
    conversation_metrics_id: UUID
    duration_seconds: float = Field(..., description="Duración en segundos")
    total_operations: int = Field(..., description="Total de operaciones realizadas")
    created_at: datetime

    class Config:
        from_attributes = True


# 🎯 Esquemas para métricas de cache

class CacheMetricsBase(BaseModel):
    """Esquema base para métricas de cache."""
    resource_type: str = Field(..., max_length=100, description="Tipo de recurso")
    resource_id: str = Field(..., max_length=255, description="ID del recurso")
    operation: str = Field(..., max_length=20, description="Tipo de operación")
    duration_ms: Optional[Decimal] = Field(None, ge=0, description="Duración en milisegundos")
    size_bytes: Optional[int] = Field(None, ge=0, description="Tamaño en bytes")
    ttl_seconds: Optional[int] = Field(None, ge=0, description="Time to live en segundos")
    cache_layer: Optional[str] = Field(None, max_length=50, description="Capa de cache")
    compression_ratio: Optional[Decimal] = Field(None, ge=0, le=1, description="Ratio de compresión")


class CacheMetricsCreate(CacheMetricsBase):
    """Esquema para crear métricas de cache."""
    conversation_metrics_id: UUID = Field(..., description="ID de las métricas de conversación")


class CacheMetricsResponse(CacheMetricsBase):
    """Esquema de respuesta para métricas de cache."""
    id: UUID
    conversation_metrics_id: UUID
    duration_seconds: Optional[float] = Field(None, description="Duración en segundos")
    size_kb: Optional[float] = Field(None, description="Tamaño en KB")
    created_at: datetime

    class Config:
        from_attributes = True


# 🎯 Esquemas para métricas de errores

class ErrorMetricsBase(BaseModel):
    """Esquema base para métricas de errores."""
    error_type: str = Field(..., max_length=100, description="Tipo de error")
    error_code: Optional[str] = Field(None, max_length=50, description="Código de error")
    error_message: str = Field(..., description="Mensaje de error")
    error_stack: Optional[str] = Field(None, description="Stack trace del error")
    step_number: Optional[int] = Field(None, ge=1, description="Número del paso donde ocurrió")
    step_type: Optional[str] = Field(None, max_length=100, description="Tipo del paso")
    user_input: Optional[str] = Field(None, description="Input del usuario que causó el error")
    severity: TelemetrySeverity = Field(TelemetrySeverity.MEDIUM, description="Severidad del error")
    recovered: bool = Field(False, description="Si el error fue recuperado")
    recovery_action: Optional[str] = Field(None, max_length=100, description="Acción de recuperación")


class ErrorMetricsCreate(ErrorMetricsBase):
    """Esquema para crear métricas de errores."""
    conversation_metrics_id: UUID = Field(..., description="ID de las métricas de conversación")


class ErrorMetricsResponse(ErrorMetricsBase):
    """Esquema de respuesta para métricas de errores."""
    id: UUID
    conversation_metrics_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# 🎯 Esquemas para métricas agregadas

class AggregatedMetricsBase(BaseModel):
    """Esquema base para métricas agregadas."""
    period_type: TelemetryPeriodType = Field(..., description="Tipo de período")
    period_start: datetime = Field(..., description="Inicio del período")
    period_end: datetime = Field(..., description="Fin del período")
    
    # Métricas agregadas
    total_conversations: int = Field(..., ge=0, description="Total de conversaciones")
    total_tokens: int = Field(..., ge=0, description="Total de tokens")
    total_cost_usd: Decimal = Field(..., ge=0, description="Costo total en USD")
    avg_latency_ms: Decimal = Field(..., ge=0, description="Latencia promedio en ms")
    avg_cache_hit_ratio: Decimal = Field(..., ge=0, le=1, description="Ratio promedio de cache")
    avg_user_satisfaction: Optional[Decimal] = Field(None, ge=1, le=5, description="Satisfacción promedio del usuario")
    
    # Métricas de errores
    total_errors: int = Field(..., ge=0, description="Total de errores")
    error_rate: Decimal = Field(..., ge=0, le=1, description="Tasa de errores")
    
    # Métricas de usuarios
    unique_users: int = Field(..., ge=0, description="Usuarios únicos")
    active_sessions: int = Field(..., ge=0, description="Sesiones activas")
    
    # Métricas de recursos
    most_accessed_databases: Optional[Dict[str, Any]] = Field(None, description="Bases de datos más accedidas")
    most_accessed_apps: Optional[Dict[str, Any]] = Field(None, description="Aplicaciones más accedidas")
    most_used_functions: Optional[Dict[str, Any]] = Field(None, description="Funciones más utilizadas")

    @validator('period_end')
    def validate_period_end_after_start(cls, v, values):
        """Valida que period_end sea posterior a period_start."""
        if 'period_start' in values and v <= values['period_start']:
            raise ValueError('period_end debe ser posterior a period_start')
        return v


class AggregatedMetricsCreate(AggregatedMetricsBase):
    """Esquema para crear métricas agregadas."""
    pass


class AggregatedMetricsResponse(AggregatedMetricsBase):
    """Esquema de respuesta para métricas agregadas."""
    id: UUID
    avg_cost_per_conversation: Decimal = Field(..., description="Costo promedio por conversación")
    avg_tokens_per_conversation: float = Field(..., description="Promedio de tokens por conversación")
    success_rate: float = Field(..., description="Tasa de éxito")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 🎯 Esquemas para respuestas de telemetría

class TelemetrySnapshotResponse(BaseModel):
    """Respuesta del snapshot de telemetría."""
    conversation_id: UUID
    metrics: ConversationMetricsResponse
    steps: List[StepMetricsResponse] = Field(default_factory=list)
    cache_operations: List[CacheMetricsResponse] = Field(default_factory=list)
    errors: List[ErrorMetricsResponse] = Field(default_factory=list)
    
    # KPIs calculados
    kpis: Dict[str, Any] = Field(..., description="Indicadores clave de performance")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field("1.0.0", description="Versión del esquema de telemetría")


class TelemetryDashboardResponse(BaseModel):
    """Respuesta del dashboard de telemetría."""
    # Métricas en tiempo real
    current_period: AggregatedMetricsResponse
    
    # Métricas históricas
    historical_data: List[AggregatedMetricsResponse] = Field(default_factory=list)
    
    # Top performers
    top_conversations: List[ConversationMetricsResponse] = Field(default_factory=list)
    top_errors: List[ErrorMetricsResponse] = Field(default_factory=list)
    
    # Tendencias
    trends: Dict[str, Any] = Field(..., description="Tendencias de métricas clave")
    
    # Alertas
    alerts: List[Dict[str, Any]] = Field(default_factory=list, description="Alertas activas")
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TelemetryExportRequest(BaseModel):
    """Solicitud de exportación de telemetría."""
    start_date: datetime = Field(..., description="Fecha de inicio")
    end_date: datetime = Field(..., description="Fecha de fin")
    format: str = Field("json", pattern="^(json|csv|excel)$", description="Formato de exportación")
    include_details: bool = Field(True, description="Incluir métricas detalladas")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtros adicionales")

    @validator('end_date')
    def validate_end_date_after_start(cls, v, values):
        """Valida que end_date sea posterior a start_date."""
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date debe ser posterior a start_date')
        return v


class TelemetryExportResponse(BaseModel):
    """Respuesta de exportación de telemetría."""
    export_id: UUID
    download_url: str = Field(..., description="URL de descarga")
    expires_at: datetime = Field(..., description="Momento de expiración")
    file_size_bytes: int = Field(..., description="Tamaño del archivo en bytes")
    record_count: int = Field(..., description="Número de registros exportados")
