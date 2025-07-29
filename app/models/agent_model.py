from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Float, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base_model import Base
from app.models.agent_app_link import AgentAppLink
from app.models.agent_database_link import AgentDatabaseLink


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=False)

    language = Column(String, nullable=True)
    temperature = Column(Float, nullable=True, default=0.7)
    max_tokens = Column(Integer, nullable=True)
    memory_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="agents")

    app_links = relationship("AgentAppLink", back_populates="agent", cascade="all, delete-orphan")
    database_links = relationship("AgentDatabaseLink", back_populates="agent", cascade="all, delete-orphan")

    chats = relationship("Chat", back_populates="agent", cascade="all, delete-orphan")
