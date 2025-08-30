from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base_model import Base


class App(Base):
    __tablename__ = "apps"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    openapi_json = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)

    mcp_integration_id = Column(UUID(as_uuid=True), ForeignKey("mcp_integrations.id"), nullable=True)
    proxy_id = Column(UUID(as_uuid=True), ForeignKey("proxies.id"), nullable=True)

    mcp_integration = relationship("MCPIntegration", back_populates="apps")
    proxy = relationship("Proxy", back_populates="apps")
    user = relationship("User", back_populates="apps")
    functions = relationship("Function", back_populates="app", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="app", cascade="all, delete-orphan")
    agent_links = relationship("AgentAppLink", back_populates="app", cascade="all, delete-orphan")
    api_triggering_configs = relationship("APITriggeringConfig", back_populates="app", cascade="all, delete-orphan")


    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
