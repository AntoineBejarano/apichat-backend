from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.models.base_model import Base
from app.models.function_call_log_model import FunctionCallLog
from app.models.executed_strategy_model import ExecutedStrategy  # ✅ Import directo

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    role = Column(String, nullable=False, index=True)  # "user", "assistant", "function", etc.
    content = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    token_count = Column(Integer, nullable=True)

    is_function_call = Column(Boolean, nullable=False, default=False)
    function_call_id = Column(UUID(as_uuid=True), ForeignKey("function_call_logs.id"), nullable=True)

    executed_strategy_id = Column(UUID(as_uuid=True), ForeignKey("executed_strategies.id"), nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # 🧠 Nuevos campos para modo explorador y contexto
    explorer = Column(Boolean, nullable=False, default=False)
    db_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])
    app_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])

    # Relaciones
    chat = relationship("Chat", back_populates="history")
    function_call = relationship("FunctionCallLog", back_populates="chat_history", uselist=False)
    executed_strategy = relationship(ExecutedStrategy, back_populates="chat_histories")

    # ⚡ ÍNDICES COMPUESTOS PARA OPTIMIZAR CONSULTAS FRECUENTES
    __table_args__ = (
        # Índice para consultas por chat_id + timestamp (historial de chat)
        Index('idx_chat_history_chat_timestamp', 'chat_id', 'timestamp'),
        
        # Índice para consultas por user_id + timestamp (historial del usuario)
        Index('idx_chat_history_user_timestamp', 'user_id', 'timestamp'),
        
        # Índice para consultas por user_id + role (system prompts)
        Index('idx_chat_history_user_role', 'user_id', 'role'),
        
        # Índice para consultas por chat_id + user_id (seguridad)
        Index('idx_chat_history_chat_user', 'chat_id', 'user_id'),
        
        # Índice para consultas por timestamp (últimos mensajes)
        Index('idx_chat_history_timestamp_desc', 'timestamp', postgresql_ops={'timestamp': 'DESC'}),
    )
