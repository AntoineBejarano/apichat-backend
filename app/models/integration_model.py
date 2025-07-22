# app/models/integration_model.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 🔑 FK a users.id

    name = Column(String, nullable=False)        # Ej: Notion, n8n
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)     # Icono para UI
    integration_metadata = Column(JSON)          # Metadatos libres
    available = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 🔗 Relación inversa a User.integrations
    user = relationship("User", back_populates="integrations")

    # Mantén tus otras relaciones, añadiendo cascades si lo deseas
    functions = relationship(
        "Function",
        back_populates="integration",
        cascade="all, delete-orphan"
    )
    oauth_accounts = relationship(
        "OAuthAccount",
        back_populates="integration",
        cascade="all, delete-orphan"
    )
