from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base_model import Base

class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    database_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id"), nullable=True)

    system_prompt = Column(Text, nullable=True)
    title = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    user = relationship("User", back_populates="chats")
    app = relationship("App")
    agent = relationship("Agent")
    database = relationship("DatabaseConnection")
    history = relationship("ChatHistory", back_populates="chat", cascade="all, delete-orphan")
    llm_runs = relationship("LLMRun", back_populates="chat", cascade="all, delete-orphan")
