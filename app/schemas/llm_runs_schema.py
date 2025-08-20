"""
🔧 FASE 6: Schemas para LLM Runs (LangSmith integration)
──────────────────────────────────────────────────────────
Schemas Pydantic para crear, actualizar y consultar LLM runs.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID
from datetime import datetime

class LLMRunBase(BaseModel):
    """Schema base para LLM runs."""
    
    chat_id: UUID
    user_id: UUID
    model_name: str = Field(..., description="Nombre del modelo LLM usado")
    model_version: Optional[str] = Field(None, description="Versión del modelo")
    provider: str = Field("openai", description="Proveedor del modelo (openai, anthropic, etc.)")
    
    # Prompt y respuesta
    prompt_text: str = Field(..., description="Texto del prompt enviado al LLM")
    response_text: str = Field(..., description="Respuesta recibida del LLM")
    
    # Tokens
    prompt_tokens: int = Field(0, description="Número de tokens en el prompt")
    response_tokens: int = Field(0, description="Número de tokens en la respuesta")
    total_tokens: int = Field(0, description="Total de tokens usados")
    
    # Funciones
    functions_invoked: Optional[Dict[str, Any]] = Field(None, description="Funciones invocadas")
    function_results: Optional[Dict[str, Any]] = Field(None, description="Resultados de funciones")
    
    # Estado
    status: str = Field("success", description="Estado de la llamada")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    response_time_ms: int = Field(..., description="Tiempo de respuesta en milisegundos")
    
    # Contexto SQL
    table_schema: Optional[str] = Field(None, description="Esquema de BD usado")
    database_id: Optional[UUID] = Field(None, description="ID de la BD consultada")
    sql_generated: Optional[str] = Field(None, description="SQL generado por el LLM")
    sql_validated: Optional[bool] = Field(None, description="Si el SQL pasó validación")
    sql_executed: Optional[bool] = Field(None, description="Si el SQL se ejecutó")
    
    @field_validator('total_tokens', mode='before')
    @classmethod
    def calculate_total_tokens(cls, v, info):
        """Calcula automáticamente el total de tokens si no se proporciona."""
        if v == 0 and info.data and 'prompt_tokens' in info.data and 'response_tokens' in info.data:
            return info.data['prompt_tokens'] + info.data['response_tokens']
        return v

class LLMRunCreate(LLMRunBase):
    """Schema para crear un nuevo LLM run."""
    pass

class LLMRunUpdate(BaseModel):
    """Schema para actualizar un LLM run existente."""
    
    status: Optional[str] = None
    error_message: Optional[str] = None
    sql_validated: Optional[bool] = None
    sql_executed: Optional[bool] = None
    function_results: Optional[Dict[str, Any]] = None

class LLMRunResponse(LLMRunBase):
    """Schema para respuestas de LLM runs."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class LLMRunListResponse(BaseModel):
    """Schema para listar LLM runs."""
    
    runs: List[LLMRunResponse]
    total: int
    page: int
    size: int
    
    model_config = ConfigDict(from_attributes=True)

class LLMRunStats(BaseModel):
    """Schema para estadísticas de LLM runs."""
    
    total_runs: int
    successful_runs: int
    failed_runs: int
    total_tokens: int
    avg_response_time_ms: float
    success_rate: float
    
    model_config = ConfigDict(from_attributes=True)
