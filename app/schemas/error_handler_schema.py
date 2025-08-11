"""
🎯 FASE 11: Esquemas para el manejo de errores con remediación automática.

Este módulo define los esquemas Pydantic para las solicitudes y respuestas
del ErrorHandlerService y su router.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class RetryActionRequest(BaseModel):
    """Solicitud para ejecutar una acción de reintento."""
    chat_id: str = Field(..., description="ID del chat donde ocurrió el error")
    action: str = Field(..., description="Acción a ejecutar (retry, switch_to_fast_mode, etc.)")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexto adicional para la acción")


class SuggestedActionResponse(BaseModel):
    """Acción sugerida en la respuesta."""
    label: str = Field(..., description="Texto visible para el usuario")
    action: str = Field(..., description="Identificador de la acción")
    description: Optional[str] = Field(None, description="Descripción de la acción")


class RetryActionResponse(BaseModel):
    """Respuesta de una acción de reintento."""
    success: bool = Field(..., description="Si la acción se ejecutó exitosamente")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    suggested_actions: List[SuggestedActionResponse] = Field(
        default_factory=list, 
        description="Acciones sugeridas adicionales"
    )
    error: Optional[str] = Field(None, description="Error si la acción falló")
    
    # Campos adicionales dinámicos
    retry_count: Optional[int] = Field(None, description="Número de reintentos realizados")
    mode: Optional[str] = Field(None, description="Modo de operación actual")
    patterns: Optional[Dict[str, Any]] = Field(None, description="Patrones de error detectados")
    recommendations: Optional[List[str]] = Field(None, description="Recomendaciones del diagnóstico")


class RecentError(BaseModel):
    """Error reciente en el historial."""
    timestamp: str = Field(..., description="Timestamp del error en formato ISO")
    code: str = Field(..., description="Código del error")
    severity: str = Field(..., description="Severidad del error")


class ErrorStatisticsResponse(BaseModel):
    """Estadísticas de errores para un chat específico."""
    chat_id: str = Field(..., description="ID del chat")
    total_errors: int = Field(..., description="Total de errores en el chat")
    retry_count: int = Field(..., description="Número de reintentos realizados")
    recent_errors: List[RecentError] = Field(
        default_factory=list, 
        description="Lista de errores recientes"
    )


class GlobalErrorStatistics(BaseModel):
    """Estadísticas globales de errores."""
    total_errors: int = Field(..., description="Total de errores en el sistema")
    total_chats_with_errors: int = Field(..., description="Total de chats con errores")
    average_errors_per_chat: float = Field(..., description="Promedio de errores por chat")
    chats_by_error_count: Dict[str, int] = Field(
        ..., 
        description="Distribución de chats por número de errores"
    )


class ErrorDiagnosisRequest(BaseModel):
    """Solicitud para diagnosticar errores de un chat."""
    chat_id: str = Field(..., description="ID del chat a diagnosticar")
    include_patterns: bool = Field(True, description="Incluir análisis de patrones")
    include_recommendations: bool = Field(True, description="Incluir recomendaciones")


class ErrorDiagnosisResponse(BaseModel):
    """Respuesta del diagnóstico de errores."""
    success: bool = Field(..., description="Si el diagnóstico se completó exitosamente")
    message: str = Field(..., description="Mensaje del diagnóstico")
    patterns: Optional[Dict[str, Any]] = Field(None, description="Patrones de error detectados")
    recommendations: Optional[List[str]] = Field(None, description="Recomendaciones del diagnóstico")
    total_errors: int = Field(..., description="Total de errores analizados")
    recent_errors: int = Field(..., description="Número de errores recientes analizados")


class ModeSwitchRequest(BaseModel):
    """Solicitud para cambiar modo de operación."""
    chat_id: str = Field(..., description="ID del chat")
    new_mode: str = Field(..., description="Nuevo modo (fast, safe, balanced)")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexto adicional")


class ModeSwitchResponse(BaseModel):
    """Respuesta del cambio de modo."""
    success: bool = Field(..., description="Si el cambio se realizó exitosamente")
    message: str = Field(..., description="Mensaje del cambio")
    mode: str = Field(..., description="Modo actual después del cambio")
    previous_mode: Optional[str] = Field(None, description="Modo anterior")
    estimated_tokens: Optional[int] = Field(None, description="Tokens estimados con el nuevo modo")
    budget_usage_percent: Optional[float] = Field(None, description="Porcentaje de uso del presupuesto")


class ErrorContext(BaseModel):
    """Contexto de un error para análisis."""
    operation: str = Field(..., description="Operación que falló")
    explorer: bool = Field(False, description="Si estaba en modo explorador")
    db_ids: Optional[List[UUID]] = Field(None, description="IDs de bases de datos involucradas")
    app_ids: Optional[List[UUID]] = Field(None, description="IDs de aplicaciones involucradas")
    user_message: Optional[str] = Field(None, description="Mensaje del usuario que causó el error")
    timestamp: str = Field(..., description="Timestamp del error")
    user_id: Optional[str] = Field(None, description="ID del usuario afectado")


class ErrorReport(BaseModel):
    """Reporte completo de un error."""
    code: str = Field(..., description="Código único del error")
    category: str = Field(..., description="Categoría del error")
    severity: str = Field(..., description="Nivel de severidad")
    human_message: str = Field(..., description="Mensaje comprensible para el usuario")
    technical_details: Optional[str] = Field(None, description="Detalles técnicos")
    suggested_actions: List[SuggestedActionResponse] = Field(..., description="Acciones sugeridas")
    retry_after: Optional[int] = Field(None, description="Segundos antes de reintentar")
    context: ErrorContext = Field(..., description="Contexto del error")
    timestamp: str = Field(..., description="Timestamp del reporte")
