from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)

    role = Column(String, nullable=False)  # "user", "assistant", "function", etc.
    content = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    token_count = Column(Integer, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    chat = relationship("Chat", back_populates="history")
