"""
🔧 FASE 6: Modelo para LLM Runs (LangSmith integration)
──────────────────────────────────────────────────────────
Modelo para almacenar cada llamada al LLM con trazabilidad completa.
"""

from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base_model import Base
import uuid

class LLMRun(Base):
    """Modelo para almacenar cada llamada al LLM con trazabilidad completa."""
    
    __tablename__ = "llm_runs"
    
    # Identificadores
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Información del LLM
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=True)
    provider = Column(String(50), nullable=False, default="openai")
    
    # Prompt y respuesta
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    response_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    
    # Funciones invocadas (si las hay)
    functions_invoked = Column(JSON, nullable=True)
    function_results = Column(JSON, nullable=True)
    
    # Estado y métricas
    status = Column(String(20), nullable=False, default="success")  # 'success', 'error', 'timeout'
    error_message = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=False)
    
    # Contexto y metadatos específicos de SQL
    table_schema = Column(Text, nullable=True)
    database_id = Column(UUID(as_uuid=True), nullable=True)
    sql_generated = Column(Text, nullable=True)
    sql_validated = Column(Boolean, nullable=True)
    sql_executed = Column(Boolean, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relaciones
    chat = relationship("Chat", back_populates="llm_runs")
    user = relationship("User", back_populates="llm_runs")
    
    def __repr__(self):
        return f"<LLMRun(id={self.id}, model={self.model_name}, status={self.status}, tokens={self.total_tokens})>"
    
    def to_dict(self):
        """Convierte el modelo a diccionario para serialización."""
        return {
            "id": str(self.id),
            "chat_id": str(self.chat_id),
            "user_id": str(self.user_id),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "provider": self.provider,
            "prompt_text": self.prompt_text,
            "response_text": self.response_text,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "total_tokens": self.total_tokens,
            "functions_invoked": self.functions_invoked,
            "function_results": self.function_results,
            "status": self.status,
            "error_message": self.error_message,
            "response_time_ms": self.response_time_ms,
            "table_schema": self.table_schema,
            "database_id": str(self.database_id) if self.database_id else None,
            "sql_generated": self.sql_generated,
            "sql_validated": self.sql_validated,
            "sql_executed": self.sql_executed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
