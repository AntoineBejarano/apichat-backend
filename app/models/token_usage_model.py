# app/models/token_usage_model.py

from sqlalchemy import Column, ForeignKey, DateTime, String, Integer, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base_model import Base
import uuid

class TokenUsage(Base):
    __tablename__ = "token_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    model = Column(String, nullable=False, index=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="token_usages")

    # ⚡ ÍNDICES COMPUESTOS PARA OPTIMIZAR CONSULTAS DE LÍMITES
    __table_args__ = (
        # Índice para consultas mensuales por usuario
        Index('idx_token_usage_user_timestamp', 'user_id', 'timestamp'),
        
        # Índice para consultas por modelo
        Index('idx_token_usage_model', 'model'),
        
        # Índice para consultas por usuario + modelo
        Index('idx_token_usage_user_model', 'user_id', 'model'),
    )
