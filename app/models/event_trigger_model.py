from sqlalchemy import Column, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4

from app.models.base_model import Base


class EventTrigger(Base):
    __tablename__ = "event_triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_definition_id = Column(UUID(as_uuid=True), ForeignKey("event_definitions.id"), nullable=False)

    config = Column(JSON, nullable=False)  # Parámetros concretos (validados por el schema de definition)

    # Relaciones
    event_definition = relationship("EventDefinition")
    triggers = relationship("Trigger", back_populates="event_trigger")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
