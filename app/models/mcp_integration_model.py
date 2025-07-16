from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import relationship

class MCPIntegration(Base):
    __tablename__ = "mcp_integrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mcp_type = Column(String, nullable=False)  # http, stdio, websocket
    mcp_metadata = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    apps = relationship("App", back_populates="mcp_integration", cascade="all, delete-orphan")
