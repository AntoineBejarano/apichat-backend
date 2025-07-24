from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from uuid import uuid4

from app.models.base_model import Base


class EventDefinition(Base):
    __tablename__ = "event_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False, unique=True)  # Ej: 'new_row_in_table'
    group = Column(String, nullable=False)              # Ej: 'database', 'webhook', etc.
    description = Column(String, nullable=True)

    schema = Column(JSON, nullable=False)  # JSON con los campos requeridos en el trigger
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
