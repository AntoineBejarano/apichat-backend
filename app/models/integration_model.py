from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Ej: Notion, n8n
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)  # Icono para UI

    integration_metadata = Column(JSON)  # ← nombre corregido
    available = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    functions = relationship("Function", back_populates="integration")
    oauth_accounts = relationship("OAuthAccount", back_populates="integration")
