from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4

from app.models.base_model import Base


class Trigger(Base):
    __tablename__ = "triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_trigger_id = Column(UUID(as_uuid=True), ForeignKey("event_triggers.id"), nullable=False)

    # Acción a ejecutar
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True)
    app_id = Column(String, nullable=True)             # Ej: 'instantly'
    function_name = Column(String, nullable=True)      # Ej: 'send_email'

    # Condiciones
    filter_condition = Column(JSON, nullable=True)     # Ej: { "country": "ES" }

    interval_seconds = Column(Integer, default=60)
    enabled = Column(Boolean, default=True)
    last_checked = Column(DateTime, nullable=True)

    event_trigger = relationship("EventTrigger", back_populates="triggers")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
