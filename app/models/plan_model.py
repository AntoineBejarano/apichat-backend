"""
Modelos de base de datos para el sistema de Planes y To-dos.
"""

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class UserPlan(Base):
    """Modelo para planes de usuario (contenedores de objetivos globales)."""
    
    __tablename__ = "user_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Información del plan
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(
        String(20), 
        nullable=False, 
        default="draft",
        server_default="draft"
    )
    priority = Column(
        String(20), 
        default="medium",
        server_default="medium"
    )
    
    # Estimaciones y métricas
    estimated_duration = Column(Integer)  # en minutos
    actual_duration = Column(Integer)     # en minutos
    
    # Metadatos
    plan_metadata = Column(JSON, default=dict, server_default="{}")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'running', 'completed', 'failed', 'paused')",
            name="user_plans_status_check"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="user_plans_priority_check"
        ),
    )
    
    # Relaciones
    user = relationship("User", back_populates="user_plans", lazy="select")
    tasks = relationship("PlanTask", back_populates="plan", cascade="all, delete-orphan")
    execution_states = relationship("PlanExecutionState", back_populates="plan", cascade="all, delete-orphan")
    outcomes = relationship("PlanOutcome", back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<UserPlan(id={self.id}, title='{self.title}', status='{self.status}')>"


class PlanTask(Base):
    """Modelo para tareas atómicas dentro de un plan."""
    
    __tablename__ = "plan_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("user_plans.id", ondelete="CASCADE"), nullable=False)
    
    # Información de la tarea
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(
        String(20), 
        nullable=False, 
        default="pending",
        server_default="pending"
    )
    
    # Orden y dependencias
    order_index = Column(Integer, nullable=False)
    dependencies = Column(JSON, default=list, server_default="[]")
    
    # Estimaciones y métricas
    estimated_effort = Column(Integer)  # en minutos
    actual_effort = Column(Integer)     # en minutos
    
    # Resultados y errores
    outcome = Column(JSON, default=dict, server_default="{}")
    errors = Column(JSON, default=list, server_default="[]")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed', 'skipped')",
            name="plan_tasks_status_check"
        ),
    )
    
    # Relaciones
    plan = relationship("UserPlan", back_populates="tasks")
    
    def __repr__(self):
        return f"<PlanTask(id={self.id}, title='{self.title}', status='{self.status}')>"


class PlanExecutionState(Base):
    """Modelo para el estado de ejecución de planes en Redis."""
    
    __tablename__ = "plan_execution_state"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("user_plans.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(255), nullable=False)
    
    # Estado de ejecución
    redis_key = Column(String(255), nullable=False)
    current_task_index = Column(Integer, default=0, server_default="0")
    status = Column(
        String(20), 
        nullable=False, 
        default="initialized",
        server_default="initialized"
    )
    
    # Metadatos de ejecución
    execution_metadata = Column(JSON, default=dict, server_default="{}")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('initialized', 'running', 'paused', 'completed', 'failed')",
            name="plan_execution_state_status_check"
        ),
    )
    
    # Relaciones
    plan = relationship("UserPlan", back_populates="execution_states")
    
    def __repr__(self):
        return f"<PlanExecutionState(id={self.id}, run_id='{self.run_id}', status='{self.status}')>"


class PlanOutcome(Base):
    """Modelo para métricas y resultados de planes completados."""
    
    __tablename__ = "plan_outcomes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("user_plans.id", ondelete="CASCADE"), nullable=False)
    
    # Métricas de ejecución
    total_tasks = Column(Integer, nullable=False)
    completed_tasks = Column(Integer, nullable=False, default=0, server_default="0")
    failed_tasks = Column(Integer, nullable=False, default=0, server_default="0")
    skipped_tasks = Column(Integer, nullable=False, default=0, server_default="0")
    
    # Tiempos
    total_estimated_time = Column(Integer)  # en minutos
    total_actual_time = Column(Integer)     # en minutos
    
    # Resultados
    success_rate = Column(Integer, default=0, server_default="0")  # porcentaje de éxito
    outcome_summary = Column(Text)
    
    # Metadatos
    execution_metadata = Column(JSON, default=dict, server_default="{}")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    plan = relationship("UserPlan", back_populates="outcomes")
    
    def __repr__(self):
        return f"<PlanOutcome(id={self.id}, plan_id={self.plan_id}, success_rate={self.success_rate}%)>"