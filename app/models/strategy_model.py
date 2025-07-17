from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.models.base_model import Base


class TriggerTypeEnum(str, enum.Enum):
    EVENT = "event"
    CRON = "cron"
    MANUAL = "manual"


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    trigger_type = Column(Enum(TriggerTypeEnum), nullable=False)
    trigger_config = Column(JSONB, nullable=True)  # Ej: {"cron": "0 0 * * *"} o {"event": "new_lead"}
    steps = Column(JSONB, nullable=False)          # Lista de pasos [{"function_id": ..., "inputs": {...}}, ...]
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")     # success, error, pending, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="strategies")
