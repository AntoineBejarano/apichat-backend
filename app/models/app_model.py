from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class App(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    openapi_json = Column(Text, nullable=True)

    is_public = Column(Boolean, default=False)

    # 🔗 Relación opcional a una integración MCP
    mcp_integration_id = Column(Integer, ForeignKey("mcp_integrations.id"), nullable=True)
    mcp_integration = relationship("MCPIntegration", backref="apps")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="apps")
    functions = relationship("Function", back_populates="app", cascade="all, delete-orphan")
