from sqlalchemy import Column, String, Boolean, JSON, Float, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.models.base_model import Base


class APITriggeringConfig(Base):
    __tablename__ = "api_triggering_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=False)
    
    # Configuración de triggering
    enabled = Column(Boolean, default=True, nullable=False)
    confidence_threshold = Column(Float, default=0.7, nullable=False)
    max_auto_executions = Column(Integer, default=5, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    
    # Control de endpoints
    allowed_endpoints = Column(JSON, default=list, nullable=True)  # Whitelist
    blocked_endpoints = Column(JSON, default=list, nullable=True)  # Blacklist
    
    # Configuración avanzada
    auto_confirm = Column(Boolean, default=False, nullable=False)  # Ejecutar sin confirmar
    require_explicit_consent = Column(Boolean, default=True, nullable=False)
    
    # Metadatos
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="api_triggering_configs")
    app = relationship("App", back_populates="api_triggering_configs")
