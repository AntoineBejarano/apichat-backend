import uuid
from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base_model import Base

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)        # Ej: Notion, n8n
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)     # Icono para UI
    integration_metadata = Column(JSON)
    available = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="integrations")

    oauth_accounts = relationship(
        "OAuthAccount",
        back_populates="integration",
        cascade="all, delete-orphan"
    )
