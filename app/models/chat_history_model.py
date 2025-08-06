from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base_model import Base
from app.models.function_call_log_model import FunctionCallLog


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    role = Column(String, nullable=False)  # "user", "assistant", "function", etc.
    content = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    token_count = Column(Integer, nullable=True)

    is_function_call = Column(Boolean, nullable=False, default=False)
    function_call_id = Column(UUID(as_uuid=True), ForeignKey("function_call_logs.id"), nullable=True)

    # 👇 Nuevo: referencia opcional a estrategia IA ejecutada
    executed_strategy_id = Column(UUID(as_uuid=True), ForeignKey("executed_strategies.id"), nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    chat = relationship("Chat", back_populates="history")
    function_call = relationship("FunctionCallLog", back_populates="chat_history", uselist=False)

    # Relación a estrategia ejecutada
    executed_strategy = relationship("ExecutedStrategy", back_populates="chat_histories")
