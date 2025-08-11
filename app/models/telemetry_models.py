"""
🎯 FASE 13: Modelos de telemetría y KPIs a nivel super pro.

Este archivo contiene todos los modelos SQLAlchemy para el sistema de telemetría
avanzado que mide el impacto UX y proporciona métricas detalladas de performance.
"""

from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, DECIMAL, JSON, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from app.models.base_model import Base
import uuid
from decimal import Decimal
from typing import Optional, Dict, Any


class ConversationMetrics(Base):
    """Métricas principales de cada conversación del chat."""
    __tablename__ = "conversation_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    chat_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Métricas de tokens y costos
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(DECIMAL(10, 6), nullable=True)
    
    # Métricas de performance
    latency_total_ms = Column(DECIMAL(10, 2), nullable=False)
    latency_llm_ms = Column(DECIMAL(10, 2), nullable=True)
    latency_db_ms = Column(DECIMAL(10, 2), nullable=True)
    latency_cache_ms = Column(DECIMAL(10, 2), nullable=True)
    
    # Métricas de cache
    cache_hit_ratio = Column(DECIMAL(5, 4), nullable=False, default=0.0)
    cache_hits = Column(Integer, nullable=False, default=0)
    cache_misses = Column(Integer, nullable=False, default=0)
    
    # Métricas de ejecución
    steps_executed = Column(Integer, nullable=False, default=0)
    confirmations_required = Column(Integer, nullable=False, default=0)
    errors_encountered = Column(Integer, nullable=False, default=0)
    
    # Métricas de UX
    mode = Column(String(50), nullable=False, index=True)
    intent_classification_confidence = Column(DECIMAL(5, 4), nullable=True)
    user_satisfaction_score = Column(Integer, nullable=True)
    
    # Métricas de recursos
    databases_accessed = Column(Integer, nullable=False, default=0)
    apps_accessed = Column(Integer, nullable=False, default=0)
    functions_executed = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    
    # Metadata
    user_agent = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    country_code = Column(String(2), nullable=True)
    timezone = Column(String(50), nullable=True)
    
    # Preferencias del usuario al momento de la conversación
    user_response_format = Column(String(50), nullable=True)
    user_detail_level = Column(String(50), nullable=True)
    user_risk_tolerance = Column(String(50), nullable=True)
    user_language = Column(String(10), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    step_metrics = relationship("StepMetrics", back_populates="conversation_metrics", cascade="all, delete-orphan")
    cache_metrics = relationship("CacheMetrics", back_populates="conversation_metrics", cascade="all, delete-orphan")
    error_metrics = relationship("ErrorMetrics", back_populates="conversation_metrics", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint('user_satisfaction_score >= 1 AND user_satisfaction_score <= 5', name='valid_satisfaction_score'),
        CheckConstraint('cache_hit_ratio >= 0.0 AND cache_hit_ratio <= 1.0', name='valid_cache_hit_ratio'),
        CheckConstraint('intent_classification_confidence >= 0.0 AND intent_classification_confidence <= 1.0', name='valid_confidence'),
    )

    @hybrid_property
    def total_tokens(self) -> int:
        """Total de tokens utilizados."""
        return self.tokens_in + self.tokens_out

    @hybrid_property
    def duration_seconds(self) -> float:
        """Duración total de la conversación en segundos."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @hybrid_property
    def cost_per_token(self) -> Decimal:
        """Costo promedio por token."""
        if self.total_tokens > 0:
            return self.estimated_cost_usd / self.total_tokens
        return Decimal('0.0')

    @hybrid_property
    def success_rate(self) -> float:
        """Tasa de éxito basada en errores encontrados."""
        if self.steps_executed > 0:
            return (self.steps_executed - self.errors_encountered) / self.steps_executed
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas a diccionario para serialización."""
        return {
            "id": str(self.id),
            "chat_id": str(self.chat_id),
            "user_id": str(self.user_id),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": float(self.estimated_cost_usd) if self.estimated_cost_usd else None,
            "latency_total_ms": float(self.latency_total_ms),
            "cache_hit_ratio": float(self.cache_hit_ratio),
            "steps_executed": self.steps_executed,
            "confirmations_required": self.confirmations_required,
            "errors_encountered": self.errors_encountered,
            "mode": self.mode,
            "duration_seconds": self.duration_seconds,
            "success_rate": self.success_rate,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class StepMetrics(Base):
    """Métricas detalladas de cada paso de ejecución."""
    __tablename__ = "step_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    conversation_metrics_id = Column(UUID(as_uuid=True), ForeignKey("conversation_metrics.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    step_type = Column(String(100), nullable=False, index=True)
    
    # Métricas del paso
    duration_ms = Column(DECIMAL(10, 2), nullable=False)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    
    # Métricas específicas del paso
    tokens_used = Column(Integer, default=0)
    cache_operations = Column(Integer, default=0)
    database_queries = Column(Integer, default=0)
    llm_calls = Column(Integer, default=0)
    
    # Metadata del paso
    step_metadata = Column(JSONB, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relaciones
    conversation_metrics = relationship("ConversationMetrics", back_populates="step_metrics")

    @hybrid_property
    def duration_seconds(self) -> float:
        """Duración del paso en segundos."""
        return float(self.duration_ms) / 1000.0

    @hybrid_property
    def total_operations(self) -> int:
        """Total de operaciones realizadas en el paso."""
        return self.cache_operations + self.database_queries + self.llm_calls

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas del paso a diccionario."""
        return {
            "id": str(self.id),
            "step_number": self.step_number,
            "step_type": self.step_type,
            "duration_ms": float(self.duration_ms),
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "error_message": self.error_message,
            "tokens_used": self.tokens_used,
            "total_operations": self.total_operations,
            "step_metadata": self.step_metadata,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class CacheMetrics(Base):
    """Métricas de operaciones de cache por recurso."""
    __tablename__ = "cache_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    conversation_metrics_id = Column(UUID(as_uuid=True), ForeignKey("conversation_metrics.id"), nullable=False)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(255), nullable=False)
    
    # Métricas de cache
    operation = Column(String(20), nullable=False, index=True)
    duration_ms = Column(DECIMAL(10, 2), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    ttl_seconds = Column(Integer, nullable=True)
    
    # Metadata
    cache_layer = Column(String(50), nullable=True)
    compression_ratio = Column(DECIMAL(5, 4), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relaciones
    conversation_metrics = relationship("ConversationMetrics", back_populates="cache_metrics")

    @hybrid_property
    def duration_seconds(self) -> Optional[float]:
        """Duración de la operación de cache en segundos."""
        if self.duration_ms:
            return float(self.duration_ms) / 1000.0
        return None

    @hybrid_property
    def size_kb(self) -> Optional[float]:
        """Tamaño del recurso en KB."""
        if self.size_bytes:
            return self.size_bytes / 1024.0
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas de cache a diccionario."""
        return {
            "id": str(self.id),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "duration_ms": float(self.duration_ms) if self.duration_ms else None,
            "duration_seconds": self.duration_seconds,
            "size_bytes": self.size_bytes,
            "size_kb": self.size_kb,
            "cache_layer": self.cache_layer,
            "compression_ratio": float(self.compression_ratio) if self.compression_ratio else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ErrorMetrics(Base):
    """Métricas de errores y recuperación."""
    __tablename__ = "error_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    conversation_metrics_id = Column(UUID(as_uuid=True), ForeignKey("conversation_metrics.id"), nullable=False)
    
    # Información del error
    error_type = Column(String(100), nullable=False, index=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=False)
    error_stack = Column(Text, nullable=True)
    
    # Contexto del error
    step_number = Column(Integer, nullable=True)
    step_type = Column(String(100), nullable=True)
    user_input = Column(Text, nullable=True)
    
    # Severidad y recuperación
    severity = Column(String(20), nullable=False, default="medium", index=True)
    recovered = Column(Boolean, default=False)
    recovery_action = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relaciones
    conversation_metrics = relationship("ConversationMetrics", back_populates="error_metrics")

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas de error a diccionario."""
        return {
            "id": str(self.id),
            "error_type": self.error_type,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "step_number": self.step_number,
            "step_type": self.step_type,
            "severity": self.severity,
            "recovered": self.recovered,
            "recovery_action": self.recovery_action,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AggregatedMetrics(Base):
    """Métricas agregadas por períodos de tiempo."""
    __tablename__ = "aggregated_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    
    # Período de agregación
    period_type = Column(String(20), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Métricas agregadas
    total_conversations = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(DECIMAL(12, 6), nullable=False, default=0.0)
    avg_latency_ms = Column(DECIMAL(10, 2), nullable=False, default=0.0)
    avg_cache_hit_ratio = Column(DECIMAL(5, 4), nullable=False, default=0.0)
    avg_user_satisfaction = Column(DECIMAL(3, 2), nullable=True)
    
    # Métricas de errores
    total_errors = Column(Integer, nullable=False, default=0)
    error_rate = Column(DECIMAL(5, 4), nullable=False, default=0.0)
    
    # Métricas de usuarios
    unique_users = Column(Integer, nullable=False, default=0)
    active_sessions = Column(Integer, nullable=False, default=0)
    
    # Métricas de recursos
    most_accessed_databases = Column(JSONB, nullable=True)
    most_accessed_apps = Column(JSONB, nullable=True)
    most_used_functions = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @hybrid_property
    def avg_cost_per_conversation(self) -> Decimal:
        """Costo promedio por conversación."""
        if self.total_conversations > 0:
            return self.total_cost_usd / self.total_conversations
        return Decimal('0.0')

    @hybrid_property
    def avg_tokens_per_conversation(self) -> float:
        """Promedio de tokens por conversación."""
        if self.total_conversations > 0:
            return self.total_tokens / self.total_conversations
        return 0.0

    @hybrid_property
    def success_rate(self) -> float:
        """Tasa de éxito basada en errores."""
        if self.total_conversations > 0:
            return (self.total_conversations - self.total_errors) / self.total_conversations
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas agregadas a diccionario."""
        return {
            "id": str(self.id),
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "total_conversations": self.total_conversations,
            "total_tokens": self.total_tokens,
            "total_cost_usd": float(self.total_cost_usd),
            "avg_latency_ms": float(self.avg_latency_ms),
            "avg_cache_hit_ratio": float(self.avg_cache_hit_ratio),
            "avg_user_satisfaction": float(self.avg_user_satisfaction) if self.avg_user_satisfaction else None,
            "total_errors": self.total_errors,
            "error_rate": float(self.error_rate),
            "success_rate": self.success_rate,
            "unique_users": self.unique_users,
            "active_sessions": self.active_sessions,
            "avg_cost_per_conversation": float(self.avg_cost_per_conversation),
            "avg_tokens_per_conversation": self.avg_tokens_per_conversation,
            "most_accessed_databases": self.most_accessed_databases,
            "most_accessed_apps": self.most_accessed_apps,
            "most_used_functions": self.most_used_functions
        }
