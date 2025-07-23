from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base_model import Base  # Usa el mismo Base que el resto


class OpenAPIIntegration(Base):
    __tablename__ = "openapi_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    title    = Column(String, nullable=False)
    version  = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    raw_json = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación inversa con User.openapi_integrations
    user = relationship("User", back_populates="openapi_integrations")
