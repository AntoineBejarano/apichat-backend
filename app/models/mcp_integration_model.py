# app/models/mcp_integration_model.py

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class MCPIntegration(Base):
    __tablename__ = "mcp_integrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mcp_type = Column(String, nullable=False)
    mcp_metadata = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # back_populates debe coincidir con el atributo en App
    apps = relationship("App", back_populates="mcp_integration", cascade="all, delete-orphan")
