from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base_model import Base

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String, nullable=False)  # "user", "assistant", "function", etc.
    content = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chat_history")