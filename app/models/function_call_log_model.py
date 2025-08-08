import uuid
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base_model import Base

class FunctionCallLog(Base):
    __tablename__ = "function_call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    function_id = Column(UUID(as_uuid=True), ForeignKey("functions.id"), nullable=False, index=True)
    token_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    chat_history = relationship(
        "ChatHistory",
        back_populates="function_call",
        uselist=False
    )

    function = relationship("Function", back_populates="calls")

    # ⚡ ÍNDICES COMPUESTOS PARA OPTIMIZAR CONSULTAS DE USO
    __table_args__ = (
        # Índice para consultas mensuales por usuario
        Index('idx_function_call_user_timestamp', 'user_id', 'timestamp'),
        
        # Índice para consultas por función
        Index('idx_function_call_function', 'function_id'),
        
        # Índice para consultas por usuario + función
        Index('idx_function_call_user_function', 'user_id', 'function_id'),
        
        # Índice para consultas por sesión
        Index('idx_function_call_session', 'session_id'),
    )
