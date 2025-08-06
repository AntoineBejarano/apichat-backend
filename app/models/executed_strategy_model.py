from sqlalchemy import Column, ForeignKey, DateTime, Boolean, Text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base_model import Base
from sqlalchemy.sql import func


class ExecutedStrategy(Base):
    __tablename__ = "executed_strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan_json = Column(Text, nullable=False)  # o JSONB si usas Postgres
    result_summary = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)
    source = Column(String, default="ai_generated")

    # Relación a ChatHistory
    chat_histories = relationship("ChatHistory", back_populates="executed_strategy")
