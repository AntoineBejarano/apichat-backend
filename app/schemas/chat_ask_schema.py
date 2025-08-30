#!/usr/bin/env python3
"""
ChatAskRequest Schema - Schema para el nuevo endpoint /chat/ask
────────────────────────────────────────────────────────────────
Implementa la Fase 5 del plan de refactorización:
- Resolución de contexto
- Intent Router
- Grounding
- Planificación
- SQL Generation
- Validación
- Ejecución
- Respuesta estructurada
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID


class ChatAskRequest(BaseModel):
    """
    Request para el endpoint /chat/ask que implementa la Fase 5 completa
    """
    
    # 🔧 FASE 5: Parámetros obligatorios
    query: str = Field(
        ...,
        description="Consulta del usuario (ej: 'Cuenta cuántos usuarios activos hay')",
        min_length=1,
        max_length=1000
    )
    
    db_id: UUID = Field(
        ...,
        description="ID de la base de datos para la consulta"
    )
    
    # 🔧 FASE 5: Parámetros opcionales
    app_id: Optional[UUID] = Field(
        None,
        description="ID de la aplicación (opcional, para contexto adicional)"
    )
    
    # 🔧 FASE 5: Parámetros de control
    max_rows: Optional[int] = Field(
        1000,
        description="Máximo número de filas a retornar",
        ge=1,
        le=10000
    )
    
    timeout_seconds: Optional[int] = Field(
        30,
        description="Timeout en segundos para la ejecución",
        ge=5,
        le=300
    )
    
    # 🔧 FASE 5: Parámetros de grounding
    grounding_method: Optional[str] = Field(
        "auto",
        description="Método de grounding: 'auto', 'structured', 'diffuse'",
        pattern="^(auto|structured|diffuse)$"
    )
    
    top_k_chunks: Optional[int] = Field(
        10,
        description="Número de chunks a usar para grounding diffuse",
        ge=1,
        le=50
    )
    
    # 🔧 FASE 5: Parámetros de planificación
    include_explanation: Optional[bool] = Field(
        True,
        description="Incluir explicación detallada del plan y SQL"
    )
    
    show_sql: Optional[bool] = Field(
        True,
        description="Mostrar el SQL generado en la respuesta"
    )
    
    # 🔧 FASE 5: Parámetros de seguridad
    allow_ddl: Optional[bool] = Field(
        False,
        description="Permitir comandos DDL (siempre False por seguridad)"
    )
    
    allow_dml: Optional[bool] = Field(
        False,
        description="Permitir comandos DML (siempre False por seguridad)"
    )
    
    # 🔧 FASE 5: Parámetros de debugging
    debug_mode: Optional[bool] = Field(
        False,
        description="Modo debug con información adicional"
    )
    
    trace_id: Optional[str] = Field(
        None,
        description="ID de traza para debugging (opcional)"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validar que la consulta no esté vacía y tenga sentido"""
        if not v or not v.strip():
            raise ValueError("La consulta no puede estar vacía")
        
        # 🔧 FASE 5: Validaciones básicas de seguridad
        dangerous_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 'TRUNCATE',
            'GRANT', 'REVOKE', 'EXECUTE', 'EXEC', 'xp_', 'sp_'
        ]
        
        query_upper = v.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"La consulta no puede contener comandos peligrosos como '{keyword}'")
        
        return v.strip()
    
    @validator('grounding_method')
    def validate_grounding_method(cls, v):
        """Validar método de grounding"""
        if v not in ['auto', 'structured', 'diffuse']:
            raise ValueError("Método de grounding debe ser 'auto', 'structured' o 'diffuse'")
        return v
    
    @validator('max_rows')
    def validate_max_rows(cls, v):
        """Validar límite de filas"""
        if v is not None and (v < 1 or v > 10000):
            raise ValueError("max_rows debe estar entre 1 y 10000")
        return v
    
    @validator('timeout_seconds')
    def validate_timeout(cls, v):
        """Validar timeout"""
        if v is not None and (v < 5 or v > 300):
            raise ValueError("timeout_seconds debe estar entre 5 y 300 segundos")
        return v
    
    class Config:
        """Configuración del schema"""
        json_schema_extra = {
            "example": {
                "query": "Cuenta cuántos usuarios activos hay en la tabla users",
                "db_id": "550e8400-e29b-41d4-a716-446655440000",
                "app_id": "550e8400-e29b-41d4-a716-446655440001",
                "max_rows": 1000,
                "timeout_seconds": 30,
                "grounding_method": "auto",
                "top_k_chunks": 10,
                "include_explanation": True,
                "show_sql": True,
                "debug_mode": False
            }
        }
        
        # 🔧 FASE 5: Configuración de validación
        validate_assignment = True
        extra = "forbid"  # No permitir campos adicionales por seguridad


class ChatAskResponse(BaseModel):
    """
    Response del endpoint /chat/ask
    """
    
    # 🔧 FASE 5: Estado de la operación
    success: bool = Field(..., description="Si la operación fue exitosa")
    status: str = Field(..., description="Estado de la operación")
    message: str = Field(..., description="Mensaje descriptivo")
    
    # 🔧 FASE 5: Resultado principal (solo si success=True)
    result: Optional[dict] = Field(
        None,
        description="Resultado de la consulta (datos, filas, columnas)"
    )
    
    # 🔧 FASE 5: Explicación y SQL
    explanation: Optional[str] = Field(
        None,
        description="Explicación detallada del plan y SQL generado"
    )
    
    sql: Optional[str] = Field(
        None,
        description="SQL generado y ejecutado"
    )
    
    sql_formatted: Optional[str] = Field(
        None,
        description="SQL formateado para mejor legibilidad"
    )
    
    # 🔧 FASE 5: Metadatos del proceso
    metadata: Optional[dict] = Field(
        None,
        description="Metadatos del proceso (intención, grounding, planificación)"
    )
    
    # 🔧 FASE 5: Métricas de performance
    performance: Optional[dict] = Field(
        None,
        description="Métricas de tiempo por etapa del proceso"
    )
    
    # 🔧 FASE 5: Contexto usado
    context: Optional[dict] = Field(
        None,
        description="Contexto usado (DB, snapshot, schema)"
    )
    
    # 🔧 FASE 5: Información de debugging
    debug_info: Optional[dict] = Field(
        None,
        description="Información adicional en modo debug"
    )
    
    # 🔧 FASE 5: Tiempo total de procesamiento
    processing_time_ms: Optional[int] = Field(
        None,
        description="Tiempo total de procesamiento en milisegundos"
    )
    
    class Config:
        """Configuración del schema de respuesta"""
        json_schema_extra = {
            "example": {
                "success": True,
                "status": "completed",
                "message": "Consulta procesada exitosamente",
                "result": {
                    "data": [{"count": 150}],
                    "row_count": 1,
                    "columns": ["count"],
                    "execution_time_ms": 45
                },
                "explanation": "Se contaron los usuarios activos en la tabla users usando un SELECT COUNT(*)",
                "sql": "SELECT COUNT(*) as count FROM users WHERE active = true",
                "sql_formatted": "SELECT COUNT(*) as count\nFROM users\nWHERE active = true;",
                "metadata": {
                    "intent_type": "db_query",
                    "intent_confidence": 0.95,
                    "grounding_method": "structured",
                    "chunks_used": 3,
                    "plan_tables": ["users"],
                    "plan_joins": []
                },
                "performance": {
                    "total_time_ms": 1250,
                    "grounding_time_ms": 45,
                    "planning_time_ms": 120,
                    "sql_generation_time_ms": 85,
                    "validation_time_ms": 25,
                    "execution_time_ms": 45
                },
                "context": {
                    "db_id": "550e8400-e29b-41d4-a716-446655440000",
                    "snapshot_id": "550e8400-e29b-41d4-a716-446655440002",
                    "schema_version": "1.0",
                    "tables_available": 15,
                    "relationships_available": 23
                },
                "processing_time_ms": 1250
            }
        }
