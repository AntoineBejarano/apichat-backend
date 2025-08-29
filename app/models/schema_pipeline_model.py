#!/usr/bin/env python3
"""
SchemaPipelineModel - Modelo para tracking del pipeline de generación de schema
──────────────────────────────────────────────────────────────────────────────
Implementa:
- Estados del pipeline por stage
- Progreso y métricas
- Logs y trazabilidad
- Sistema de reintentos
"""

import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import BaseTable


class SchemaPipelineStage:
    """Enum de stages del pipeline"""
    
    # Stages estandarizados según el plan
    VALIDATE_DB_ACCESS = "validate_db_access"
    EXTRACT_SCHEMA_SNAPSHOT = "extract_schema_snapshot"
    BUILD_GRAPH = "build_graph"
    GENERATE_CHUNKS = "generate_chunks"
    EMBED_CHUNKS = "embed_chunks"
    VECTOR_UPSERT = "vector_upsert"
    FINALIZE_SNAPSHOT_ACTIVE = "finalize_snapshot_active"


class SchemaPipelineStatus:
    """Enum de estados del pipeline"""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SchemaPipeline(BaseTable):
    """Modelo principal para tracking del pipeline de schema"""
    
    __tablename__ = "schema_pipelines"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    database_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 🔧 FASE 1: Estado y progreso del pipeline
    status = Column(String, nullable=False, default=SchemaPipelineStatus.PENDING)
    current_stage = Column(String, nullable=True)
    progress_pct = Column(Integer, nullable=False, default=0)
    
    # 🔧 FASE 1: Información de errores
    error_code = Column(String, nullable=True)
    error_detail = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    
    # 🔧 FASE 1: Timing y reintentos
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # 🔧 FASE 1: Metadata del pipeline
    trace_id = Column(String, nullable=True, index=True, comment="ID único para trazabilidad")
    version = Column(String, nullable=False, default="1.0")
    
    # 🔧 FASE 1: Configuración del pipeline
    timeout_seconds = Column(Integer, nullable=False, default=600, comment="Timeout total en segundos")
    stage_timeout_seconds = Column(Integer, nullable=False, default=120, comment="Timeout por stage en segundos")
    
    # 🔧 FASE 1: Resultados del pipeline
    schema_snapshot_id = Column(UUID(as_uuid=True), nullable=True, comment="ID del snapshot generado")
    total_tables = Column(Integer, nullable=True)
    total_columns = Column(Integer, nullable=True)
    total_relationships = Column(Integer, nullable=True)
    total_chunks = Column(Integer, nullable=True)
    
    # 🔧 FASE 1: Logs estructurados
    stage_logs = Column(JSON, nullable=True, comment="Logs por stage con timestamps")
    
    # Timestamps estándar
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    database = relationship("DatabaseConnection", back_populates="schema_pipelines")
    user = relationship("User", back_populates="schema_pipelines")
    
    def __repr__(self):
        return f"<SchemaPipeline(id={self.id}, status={self.status}, stage={self.current_stage}, progress={self.progress_pct}%)>"
    
    @property
    def is_running(self) -> bool:
        """Verifica si el pipeline está ejecutándose"""
        return self.status == SchemaPipelineStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """Verifica si el pipeline se completó exitosamente"""
        return self.status == SchemaPipelineStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Verifica si el pipeline falló"""
        return self.status == SchemaPipelineStatus.FAILED
    
    @property
    def can_retry(self) -> bool:
        """Verifica si se puede reintentar el pipeline"""
        return (self.status == SchemaPipelineStatus.FAILED and 
                self.retry_count < self.max_retries)
    
    @property
    def elapsed_time_seconds(self) -> int:
        """Calcula el tiempo transcurrido en segundos"""
        if not self.started_at:
            return 0
        
        end_time = self.finished_at or func.now()
        return int((end_time - self.started_at).total_seconds())
    
    @property
    def remaining_time_seconds(self) -> int:
        """Calcula el tiempo restante estimado"""
        if not self.started_at or self.progress_pct == 0:
            return self.timeout_seconds
        
        elapsed = self.elapsed_time_seconds
        if self.progress_pct > 0:
            estimated_total = (elapsed * 100) / self.progress_pct
            remaining = estimated_total - elapsed
            return max(0, int(remaining))
        
        return self.timeout_seconds - elapsed
