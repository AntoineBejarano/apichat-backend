from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base
from app.models.function_call_log_model import FunctionCallLog  # Asegura la importación

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)

    role = Column(String, nullable=False)       # "user", "assistant", "function", etc.
    content = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    token_count = Column(Integer, nullable=True)

    # Nuevo campo para llamadas a función
    is_function_call = Column(Boolean, nullable=False, default=False)
    function_call_id = Column(Integer, ForeignKey("function_call_logs.id"), nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    chat = relationship("Chat", back_populates="history")
    function_call = relationship(
        "FunctionCallLog",
        back_populates="chat_history",
        uselist=False
    )
