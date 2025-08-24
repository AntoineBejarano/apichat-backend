"""
🔄 User Session Mode Model: Persistencia de modo por sesión

Modelo para almacenar y gestionar el modo activo (Explorer/Guided/Auto) 
por usuario y chat, con TTL configurable y fallback inteligente.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.core.database import Base


class UserSessionMode(Base):
    """
    🎯 Tabla para persistir el modo activo por usuario y chat
    
    Permite:
    - Recordar el modo preferido del usuario
    - Transiciones suaves entre modos
    - Fallback inteligente en caso de error
    - TTL configurable por tipo de sesión
    """
    
    __tablename__ = "user_session_mode"
    
    # Identificadores
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    chat_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # NULL = modo global del usuario
    
    # Modo y estado
    current_mode = Column(String(20), nullable=False, default="auto")  # explorer, guided, auto
    previous_mode = Column(String(20), nullable=True)  # Modo anterior para rollback
    mode_confidence = Column(String(10), nullable=True)  # high, medium, low
    
    # Metadatos de la sesión
    session_start = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Configuración de TTL
    ttl_hours = Column(String(10), default="24")  # TTL en horas (24, 48, 168, 0=sin expiración)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Contexto y preferencias
    user_preferences = Column(Text, nullable=True)  # JSON de preferencias del usuario
    context_summary = Column(Text, nullable=True)   # Resumen del contexto actual
    
    # Estadísticas de uso
    mode_usage_count = Column(String(10), default="0")  # Contador de uso del modo
    transition_count = Column(String(10), default="0")  # Contador de transiciones
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relaciones (opcionales)
    # user = relationship("User", back_populates="session_modes")
    # chat = relationship("Chat", back_populates="session_mode")
    
    def __repr__(self):
        return f"<UserSessionMode(user_id={self.user_id}, chat_id={self.chat_id}, mode={self.current_mode})>"
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "chat_id": str(self.chat_id) if self.chat_id else None,
            "current_mode": self.current_mode,
            "previous_mode": self.previous_mode,
            "mode_confidence": self.mode_confidence,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "is_active": self.is_active,
            "ttl_hours": self.ttl_hours,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "user_preferences": self.user_preferences,
            "context_summary": self.context_summary,
            "mode_usage_count": self.mode_usage_count,
            "transition_count": self.transition_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expired(self) -> bool:
        """Verifica si la sesión ha expirado"""
        if not self.expires_at:
            return False
        
        return datetime.utcnow() > self.expires_at
    
    def should_refresh(self) -> bool:
        """Verifica si la sesión debe refrescarse"""
        if not self.last_activity:
            return True
        
        # Refrescar si han pasado más de 1 hora sin actividad
        refresh_threshold = timedelta(hours=1)
        return datetime.utcnow() - self.last_activity > refresh_threshold
    
    def calculate_expiry(self) -> datetime:
        """Calcula la fecha de expiración basada en TTL"""
        if self.ttl_hours == "0":
            return None  # Sin expiración
        
        try:
            ttl_hours = int(self.ttl_hours)
            return datetime.utcnow() + timedelta(hours=ttl_hours)
        except (ValueError, TypeError):
            # Fallback a 24 horas
            return datetime.utcnow() + timedelta(hours=24)
    
    def update_activity(self):
        """Actualiza la actividad de la sesión"""
        self.last_activity = datetime.utcnow()
        
        # Recalcular expiración si es necesario
        if self.ttl_hours != "0":
            self.expires_at = self.calculate_expiry()
    
    def transition_to_mode(self, new_mode: str, confidence: str = "medium"):
        """Transición a un nuevo modo"""
        if new_mode != self.current_mode:
            self.previous_mode = self.current_mode
            self.current_mode = new_mode
            self.mode_confidence = confidence
            
            # Incrementar contadores
            try:
                self.mode_usage_count = str(int(self.mode_usage_count or "0") + 1)
                self.transition_count = str(int(self.transition_count or "0") + 1)
            except (ValueError, TypeError):
                self.mode_usage_count = "1"
                self.transition_count = "1"
            
            # Actualizar actividad
            self.update_activity()
    
    def rollback_mode(self) -> bool:
        """Revierte al modo anterior si es posible"""
        if self.previous_mode and self.previous_mode != self.current_mode:
            self.current_mode = self.previous_mode
            self.previous_mode = None
            self.mode_confidence = "low"  # Confianza baja en rollback
            self.update_activity()
            return True
        return False
    
    def get_mode_info(self) -> dict:
        """Obtiene información del modo actual"""
        return {
            "current_mode": self.current_mode,
            "previous_mode": self.previous_mode,
            "confidence": self.mode_confidence,
            "is_active": self.is_active,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "usage_count": self.mode_usage_count,
            "transition_count": self.transition_count
        }


# Índices para optimizar consultas
Index("idx_user_session_mode_user_chat", "user_id", "chat_id")
Index("idx_user_session_mode_current_mode", "current_mode")
Index("idx_user_session_mode_is_active", "is_active")
Index("idx_user_session_mode_expires_at", "expires_at")
Index("idx_user_session_mode_last_activity", "last_activity")
