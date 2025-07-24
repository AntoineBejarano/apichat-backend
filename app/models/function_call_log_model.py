import uuid
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base_model import Base

class FunctionCallLog(Base):
    __tablename__ = "function_call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    function_id = Column(UUID(as_uuid=True), ForeignKey("functions.id"), nullable=False)
    token_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    chat_history = relationship(
        "ChatHistory",
        back_populates="function_call",
        uselist=False
    )

    function = relationship("Function", back_populates="calls")
